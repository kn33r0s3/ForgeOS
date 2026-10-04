import assert from "node:assert/strict";
import { describe, it } from "node:test";
import { loadExecutionActions, loadMoneyDashboard } from "./operations-data.ts";

describe("owner operations requests", () => {
  it("sends the owner key to both protected dashboard reads", async () => {
    const originalFetch = globalThis.fetch;
    const requests: RequestInit[] = [];
    globalThis.fetch = async (_input, init) => {
      requests.push(init ?? {});
      return new Response("{}", {
        headers: { "Content-Type": "application/json" },
      });
    };

    try {
      await loadMoneyDashboard("TEST-owner-key", { fresh: true });
      await loadExecutionActions("TEST-owner-key", { fresh: true });
    } finally {
      globalThis.fetch = originalFetch;
    }

    assert.equal(requests.length, 2);
    for (const request of requests) {
      assert.equal(new Headers(request.headers).get("X-API-Key"), "TEST-owner-key");
    }
  });
});