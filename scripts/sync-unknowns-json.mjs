#!/usr/bin/env node
// Regenerates backend/app/data/unknowns.json from docs/UNKNOWN_MAP.md.
// Run after editing the unknowns map. The JSON is what the deployed API reads.
import { readFileSync, writeFileSync, mkdirSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const root = join(dirname(fileURLToPath(import.meta.url)), "..");
const md = readFileSync(join(root, "docs/UNKNOWN_MAP.md"), "utf8");

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
          question: parts[2],
          state: m[1],
          cheapest_test: parts[4],
          stake: parts[5],
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
console.log(`Synced ${unknowns.length} unknowns to backend/app/data/unknowns.json`);
