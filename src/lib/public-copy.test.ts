import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { describe, it } from "node:test";

/**
 * Public copy may not contain claims the API doesn't back.
 *
 * Every displayed item on the public site must come from the API with a
 * source and a truth label. This test fails if a public route:
 *  - imports a hand-written data module (findings baked into the bundle),
 *  - contains claim phrases (results, guarantees, social proof) that no
 *    API backs, or
 *  - renders engine data without importing the API module that carries
 *    its source and truth label.
 */
const PUBLIC_ROUTES: Array<{ path: string; file: string }> = [
  { path: "/", file: "src/routes/index.tsx" },
  { path: "/needs", file: "src/routes/needs.tsx" },
  { path: "/unknowns", file: "src/routes/unknowns.tsx" },
  { path: "/about", file: "src/routes/about.tsx" },
];

// Hand-written data modules: findings baked into the bundle. Public
// routes must read from the API instead. Matched as full import paths.
const BANNED_IMPORTS = ["@/lib/unknowns\"", "@/lib/unknowns'", "@/lib/needs\"", "@/lib/needs'"];

// Claim phrases no API backs. Honest-state phrases ("no merchants served
// yet", "pre-revenue", "no week has run yet") are deliberately absent.
const CLAIM_PATTERNS: RegExp[] = [
  /\bproven\b/i,
  /guaranteed/i,
  /trusted by/i,
  /\b\d+\+?\s+merchants\s+served/i,
  /\bwe('|’ve| have) recovered\b/i,
  /Rs\.?\s?\d[\d,]*\s+(recovered|earned|paid)/i,
  /₨\s?\d[\d,]*\s+(recovered|earned|paid)/i,
  /Nepal first/i,
  /sign up.*free trial/i,
];

// Routes that render engine data must import the API module carrying
// source + truth label.
const API_BACKED: Array<{ file: string; apiModule: string }> = [
  { file: "src/routes/unknowns.tsx", apiModule: "@/lib/unknowns-api" },
];

function read(file: string): string {
  return readFileSync(new URL(`../../${file}`, import.meta.url), "utf8");
}

describe("public copy is backed by the API", () => {
  for (const route of PUBLIC_ROUTES) {
    it(`${route.path}: no hand-written data imports`, () => {
      const src = read(route.file);
      for (const banned of BANNED_IMPORTS) {
        assert.ok(
          !src.includes(banned),
          `${route.path} imports hand-written data (${banned}) — read from the API instead`,
        );
      }
    });

    it(`${route.path}: no unbacked claim phrases`, () => {
      const src = read(route.file);
      for (const pattern of CLAIM_PATTERNS) {
        assert.ok(
          !pattern.test(src),
          `${route.path} contains an unbacked claim matching ${pattern}`,
        );
      }
    });
  }

  for (const entry of API_BACKED) {
    it(`${entry.file}: engine data comes through its API module`, () => {
      const src = read(entry.file);
      assert.ok(
        src.includes(entry.apiModule),
        `${entry.file} renders engine data without ${entry.apiModule} (source + truth label)`,
      );
    });
  }
});
