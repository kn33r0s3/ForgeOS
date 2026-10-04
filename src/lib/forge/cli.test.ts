import assert from "node:assert/strict";
import { execFileSync } from "node:child_process";
import { describe, it } from "node:test";

const CLI = "src/lib/forge/cli.ts";
const NODE = process.execPath;
const FLAGS = ["--experimental-strip-types"];

function run(args: string[], stdin?: string): { stdout: string; code: number } {
  try {
    const stdout = execFileSync(NODE, [...FLAGS, CLI, ...args], {
      input: stdin,
      encoding: "utf8",
      cwd: new URL("../../../", import.meta.url),
    });
    return { stdout, code: 0 };
  } catch (e: unknown) {
    const err = e as { stdout?: string; status?: number };
    return { stdout: err.stdout ?? "", code: err.status ?? 1 };
  }
}

describe("forge cli — ForgeBot v1 tools", () => {
  it("angles returns value-ranked untried angles as JSON", () => {
    const { stdout, code } = run(["angles", "--limit", "3"]);
    assert.equal(code, 0);
    const { angles } = JSON.parse(stdout) as {
      angles: Array<{ id: string; valueTier: number; valueWhy: string }>;
    };
    assert.equal(angles.length, 3);
    for (const a of angles) {
      assert.match(a.id, /^D\d+$/);
      assert.ok([1, 2, 3].includes(a.valueTier));
      assert.ok(a.valueWhy.length > 10);
    }
    // value-ranked: tiers never increase down the list
    for (let k = 1; k < angles.length; k++) {
      assert.ok(angles[k].valueTier <= angles[k - 1].valueTier);
    }
  });

  it("tried distinguishes tried ground from new ground", () => {
    assert.equal(run(["tried", "the COD courier and cash on delivery"]).stdout.trim(), "1");
    assert.equal(run(["tried", "lunar masonry techniques in Mustang"]).stdout.trim(), "0");
  });

  it("gate verifies good findings and rejects bad ones", () => {
    const good = JSON.stringify([
      {
        statement: "CLI gate test finding",
        evidenceClass: "observed",
        sources: ["Nepali business press"],
        confidence: "medium",
        weakestLink: "Single source",
        unknownIds: ["D60"],
      },
    ]);
    const okRes = run(["gate"], good);
    assert.equal(okRes.code, 0);
    assert.match(okRes.stdout, /CLI gate test finding/);

    const bad = JSON.stringify([
      {
        statement: "Ungated rumor",
        evidenceClass: "reported",
        sources: [],
        confidence: "high",
        weakestLink: "",
        unknownIds: ["D60"],
      },
    ]);
    const badRes = run(["gate"], bad);
    assert.equal(badRes.code, 2);
    assert.match(badRes.stdout, /rejected/);
  });
});
