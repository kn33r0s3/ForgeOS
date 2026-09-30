import assert from "node:assert/strict";
import { describe, it } from "node:test";
import {
  STORAGE_KEY,
  emptyState,
  hasAnyState,
  loadState,
  parseList,
  parseState,
  saveState,
  stated,
  type SystemState,
} from "./state.ts";
import { derivePaths, deriveStages, relevantFeed } from "./paths.ts";

function memoryStorage() {
  const map = new Map<string, string>();
  return {
    getItem: (k: string) => map.get(k) ?? null,
    setItem: (k: string, v: string) => void map.set(k, v),
    removeItem: (k: string) => void map.delete(k),
    map,
  };
}

function withState(patch: Partial<SystemState>): SystemState {
  return { ...emptyState("2026-01-01T00:00:00.000Z"), ...patch };
}

describe("system state", () => {
  it("round-trips through storage", () => {
    const s = memoryStorage();
    const state = withState({
      location: stated("Pokhara"),
      capabilities: [stated("Plumbing")],
      goals: [stated("earn_more" as const)],
    });
    saveState(s, state);
    const back = loadState(s);
    assert.equal(back?.location?.value, "Pokhara");
    assert.equal(back?.capabilities[0]?.value, "Plumbing");
    assert.equal(back?.goals[0]?.value, "earn_more");
  });

  it("never trusts client-side 'verified' provenance", () => {
    const raw = JSON.stringify({
      version: 1,
      location: { value: "Kathmandu", provenance: "verified", updatedAt: "x" },
      capabilities: [{ value: "Welding", provenance: "verified", updatedAt: "x" }],
      resources: [],
      goals: [],
      constraints: [],
    });
    const state = parseState(raw)!;
    assert.equal(state.location?.provenance, "stated");
    assert.equal(state.capabilities[0]?.provenance, "stated");
  });

  it("drops malformed and unknown values", () => {
    assert.equal(parseState("not json"), null);
    assert.equal(parseState(JSON.stringify({ version: 2 })), null);
    const state = parseState(
      JSON.stringify({
        version: 1,
        time: { value: "forever", provenance: "stated", updatedAt: "x" },
        goals: [{ value: "rule_the_world", provenance: "stated", updatedAt: "x" }],
        capabilities: [{ value: "   ", provenance: "stated", updatedAt: "x" }, "junk"],
      }),
    )!;
    assert.equal(state.time, undefined);
    assert.deepEqual(state.goals, []);
    assert.deepEqual(state.capabilities, []);
    assert.equal(hasAnyState(state), false);
  });

  it("parses lists uniquely and bounded", () => {
    assert.deepEqual(parseList("Driving, driving,\n  cooking  ,,"), ["Driving", "cooking"]);
    assert.equal(parseList(Array.from({ length: 60 }, (_, i) => `x${i}`).join(",")).length, 24);
  });

  it("uses a versioned, local-only key", () => {
    assert.equal(STORAGE_KEY, "hami.system.v1");
  });
});

describe("possibility paths", () => {
  it("are always 'possible' with unknowns and a next step", () => {
    const paths = derivePaths(
      withState({
        location: stated("Butwal"),
        capabilities: [stated("Electrician")],
        resources: [stated("motorbike"), stated("empty shop shutter")],
        goals: [stated("earn_more" as const), stated("grow_skills" as const)],
      }),
    );
    assert.ok(paths.length >= 4);
    for (const p of paths) {
      assert.equal(p.epistemic, "possible");
      assert.ok(p.unknowns.length > 0, `${p.id} lists unknowns`);
      assert.ok(p.nextStep.length > 0);
      assert.ok(p.from.length > 0, `${p.id} explains its origin`);
    }
    assert.ok(paths.some((p) => p.id === "resource:vehicle"));
    assert.ok(paths.some((p) => p.id === "resource:space"));
    assert.ok(paths.some((p) => p.id.startsWith("combo:")));
  });

  it("never claims money, customers or demand as fact", () => {
    const paths = derivePaths(
      withState({
        capabilities: [stated("Tailoring")],
        resources: [stated("sewing machine")],
        goals: [stated("earn_more" as const), stated("start_or_grow_business" as const)],
      }),
    );
    const text = paths.map((p) => `${p.title} ${p.why}`).join(" ");
    assert.doesNotMatch(text, /\b(guaranteed|you will earn|customers are waiting|verified demand|rs\.?\s*\d|npr\s*\d|\$\d)/i);
  });

  it("empty state yields no invented paths", () => {
    assert.deepEqual(derivePaths(emptyState()), []);
  });
});

describe("relevance", () => {
  const item = (id: string, title: string, summary = "") => ({
    id,
    kind: "signal",
    entity_type: "signal",
    entity_id: 1,
    title,
    summary,
    epistemic_state: "observed",
    relations: [],
  });

  it("explains relevance with shared words only", () => {
    const state = withState({ capabilities: [stated("solar panel installation")] });
    const out = relevantFeed(state, [item("a", "Solar irrigation pumps in Terai"), item("b", "Fiscal policy review")]);
    assert.equal(out.length, 1);
    assert.equal(out[0]!.item.id, "a");
    assert.deepEqual(out[0]!.shared, ["solar"]);
  });

  it("returns nothing when the person has told Hami nothing", () => {
    assert.deepEqual(relevantFeed(emptyState(), [item("a", "Anything")]), []);
  });
});

describe("progression", () => {
  it("evidenced stage cannot be reached from client state", () => {
    const full = withState({
      location: stated("Dharan"),
      time: stated("full_time" as const),
      goals: [stated("earn_more" as const)],
      capabilities: [stated("Driving")],
      resources: [stated("van")],
    });
    const stages = deriveStages(full, { recordedRequests: 99 });
    assert.equal(stages.find((s) => s.id === "context")?.reached, true);
    assert.equal(stages.find((s) => s.id === "capabilities")?.reached, true);
    assert.equal(stages.find((s) => s.id === "action")?.reached, true);
    const evidence = stages.find((s) => s.id === "evidence")!;
    assert.equal(evidence.reached, false);
    assert.equal(evidence.evidenceGated, true);
  });
});
