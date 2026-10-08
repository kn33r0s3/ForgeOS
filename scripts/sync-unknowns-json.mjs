#!/usr/bin/env node
// Regenerates the backend API data and the TypeScript discovery projection
// from docs/UNKNOWN_MAP.md. Run after editing the authoritative map.
import { readFileSync, writeFileSync, mkdirSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const root = join(dirname(fileURLToPath(import.meta.url)), "..");
const md = readFileSync(join(root, "docs/UNKNOWN_MAP.md"), "utf8");
const tsPath = join(root, "src/lib/unknowns.ts");
const previousTs = readFileSync(tsPath, "utf8");

function stripMd(s) {
  return s.replace(/\*\*(.+?)\*\*/g, "$1").replace(/\*(.+?)\*/g, "$1");
}

const STATES = ["UNKNOWN","HYPOTHESIZED","TESTED","SUPPORTED","CONTRADICTED","BLOCKED_BY_MISSING_ACCESS"];
const unknowns = [];
let inTable = false;
for (const line of md.split("\n")) {
  if (line.startsWith("| # |")) { inTable = true; continue; }
  if (line.startsWith("|---")) continue;
  if (inTable && line.startsWith("|")) {
    const parts = line.split("|").map(p => p.trim());
    if (parts.length >= 6 && /^[A-Z]\d+$/.test(parts[1])) {
      const m = parts[3].match(new RegExp(`^(${STATES.join("|")})`));
      if (m) {
        unknowns.push({
          id: parts[1],
          category: parts[1][0],
          question: stripMd(parts[2]),
          state: m[1],
          state_note: stripMd(parts[3]),
          cheapest_test: stripMd(parts[4]),
          stake: stripMd(parts[5]),
        });
      }
    }
  } else if (inTable && line.trim() && !line.startsWith("|")) {
    inTable = false;
  }
}

const dateMatch = md.match(/\*\*Date:\*\*\s*(\d{4}-\d{2}-\d{2})/);
const out = { unknowns, last_loop: dateMatch ? dateMatch[1] : null };

const dir = join(root, "backend/app/data");
mkdirSync(dir, { recursive: true });
writeFileSync(join(dir, "unknowns.json"), JSON.stringify(out, null, 1) + "\n");

const previousRounds = new Map();
for (const match of previousTs.matchAll(/\{\s*id:\s*"(D\d+)",([\s\S]*?)\n {2}\},/g)) {
  const round = match[2].match(/\bround:\s*(\d+)/);
  if (round) previousRounds.set(match[1], Number(round[1]));
}

const STATE_MAP = {
  UNKNOWN: "unknown",
  HYPOTHESIZED: "hypothesized",
  TESTED: "tested",
  SUPPORTED: "supported",
  CONTRADICTED: "contradicted",
  BLOCKED_BY_MISSING_ACCESS: "blocked",
};
const discoveryUnknowns = unknowns
  .filter((item) => item.id.startsWith("D"))
  .map((item) => ({
    id: item.id,
    question: item.question,
    state: STATE_MAP[item.state] ?? "unknown",
    stateNote: item.state_note,
    cheapestTest: item.cheapest_test,
    stakes: item.stake,
    round: previousRounds.get(item.id) ?? null,
  }));

const tsRows = discoveryUnknowns.map((item) => `  {
    id: ${JSON.stringify(item.id)},
    question: ${JSON.stringify(item.question)},
    state: ${JSON.stringify(item.state)},
    stateNote: ${JSON.stringify(item.stateNote)},
    cheapestTest: ${JSON.stringify(item.cheapestTest)},
    stakes: ${JSON.stringify(item.stakes)},
    round: ${item.round === null ? "null" : item.round},
  },`).join("\n");
const ts = `// Generated from docs/UNKNOWN_MAP.md by scripts/sync-unknowns-json.mjs.
// The map is authoritative; do not hand-edit this projection.

export type UnknownState =
  | "unknown"
  | "hypothesized"
  | "tested"
  | "supported"
  | "contradicted"
  | "blocked";

export interface DiscoveryUnknown {
  id: string;
  question: string;
  state: UnknownState;
  stateNote: string;
  cheapestTest: string;
  stakes: string;
  round: number | null;
}

export const discoveryUnknowns: DiscoveryUnknown[] = [
${tsRows}
];

export const unknownsCount = discoveryUnknowns.length;
`;
writeFileSync(tsPath, ts);
console.log(
  `Synced ${unknowns.length} unknowns to backend/app/data/unknowns.json and ${discoveryUnknowns.length} D-unknowns to src/lib/unknowns.ts`,
);
