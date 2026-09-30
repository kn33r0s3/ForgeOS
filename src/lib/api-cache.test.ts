import assert from "node:assert/strict";
import { describe, it } from "node:test";
import { createReadCache } from "./api-cache.ts";

/** Controllable clock so TTL boundaries are exercised without sleeping. */
function fakeClock(start = 1_000) {
  let value = start;
  return {
    now: () => value,
    advance(ms: number) {
      value += ms;
    },
  };
}

function counter<T>(value: T) {
  let calls = 0;
  return {
    get calls() {
      return calls;
    },
    load: async () => {
      calls += 1;
      return value;
    },
  };
}

describe("read cache", () => {
  it("serves a repeat read from memory inside the TTL", async () => {
    const clock = fakeClock();
    const cache = createReadCache({ now: clock.now });
    const source = counter({ ok: true });

    const first = await cache.read("feed", source.load);
    clock.advance(19_000);
    const second = await cache.read("feed", source.load);

    assert.deepEqual(first, { ok: true });
    assert.deepEqual(second, { ok: true });
    assert.equal(source.calls, 1, "a read inside the TTL must not hit the network again");
  });

  it("re-reads once the TTL has passed", async () => {
    const clock = fakeClock();
    const cache = createReadCache({ now: clock.now, freshTtlMs: 20_000 });
    const source = counter([1]);

    await cache.read("feed", source.load);
    clock.advance(20_000);
    await cache.read("feed", source.load);

    assert.equal(source.calls, 2);
  });

  it("shares one request between concurrent callers", async () => {
    const cache = createReadCache();
    let calls = 0;
    let release: (value: string) => void = () => {};
    const load = () => {
      calls += 1;
      return new Promise<string>((resolve) => {
        release = resolve;
      });
    };

    const a = cache.read("runtime", load);
    const b = cache.read("runtime", load);
    release("snapshot");

    assert.equal(await a, "snapshot");
    assert.equal(await b, "snapshot");
    assert.equal(calls, 1, "two pages asking at once must produce one request");
  });

  it("treats a null result as 'could not be checked' with a shorter life", async () => {
    const clock = fakeClock();
    const cache = createReadCache({ now: clock.now, missingTtlMs: 5_000, freshTtlMs: 20_000 });
    const source = counter<null>(null);

    await cache.read("unavailable", source.load);
    clock.advance(4_000);
    await cache.read("unavailable", source.load);
    assert.equal(source.calls, 1, "a recent failure is reused briefly to stop a retry storm");

    clock.advance(1_000);
    await cache.read("unavailable", source.load);
    assert.equal(source.calls, 2, "after the short window the failure is re-checked");
  });

  it("always re-reads when asked for fresh data, and refreshes the entry", async () => {
    const clock = fakeClock();
    const cache = createReadCache({ now: clock.now });
    let calls = 0;
    const load = async () => ({ version: ++calls });

    await cache.read("runtime", load);
    const forced = await cache.read("runtime", load, { fresh: true });
    assert.deepEqual(forced, { version: 2 });
    assert.equal(calls, 2, "a retry button must reach the network");

    const afterRetry = await cache.read("runtime", load);
    assert.deepEqual(afterRetry, { version: 2 }, "the retry result becomes the new cached value");
    assert.equal(calls, 2);
  });

  it("never caches a thrown error", async () => {
    const cache = createReadCache();
    let calls = 0;
    const load = async () => {
      calls += 1;
      throw new Error(`HTTP 503 (attempt ${calls})`);
    };

    await assert.rejects(() => cache.read("runtime", load), /attempt 1/);
    await assert.rejects(() => cache.read("runtime", load), /attempt 2/);
    assert.equal(calls, 2, "an exception stays a live signal");
  });

  it("invalidates by prefix, and everything without one", async () => {
    const cache = createReadCache();
    const publicFeed = counter(["row"]);
    const runtime = counter({ pending: 0 });

    await cache.read("public:/feed?limit=40", publicFeed.load);
    await cache.read("/api/forge/runtime", runtime.load);

    cache.invalidate("public:");
    await cache.read("public:/feed?limit=40", publicFeed.load);
    await cache.read("/api/forge/runtime", runtime.load);
    assert.equal(publicFeed.calls, 2);
    assert.equal(runtime.calls, 1, "an unrelated key survives a scoped invalidation");

    cache.invalidate();
    await cache.read("/api/forge/runtime", runtime.load);
    assert.equal(runtime.calls, 2);
  });

  it("runs straight through when caching is disabled (the SSR path)", async () => {
    const cache = createReadCache({ enabled: false });
    const source = counter("value");

    await cache.read("feed", source.load);
    await cache.read("feed", source.load);
    assert.equal(source.calls, 2);
  });
});
