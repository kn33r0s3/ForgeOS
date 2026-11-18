import { spawnSync } from "node:child_process";
import { readFileSync, existsSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

/**
 * `npm run gates` — the daily gate check (step 7 of the gates order).
 *
 * Runs the bypass tests (src/lib/gates.test.ts) and verifies the committed
 * docs/GATES.md is fresh (regenerate and diff). Prints one line, GREEN or
 * RED, and exits 0 on green, 1 on red. On red the daily check notifies the
 * owner over Telegram; otherwise it stays silent (see docs/GATES.md).
 */

const repoRoot = join(dirname(fileURLToPath(import.meta.url)), "..");
let red = [];

// 1. The bypass tests.
const test = spawnSync(
  process.execPath,
  ["--experimental-strip-types", "--test", "src/lib/gates.test.ts"],
  { cwd: repoRoot, encoding: "utf-8" },
);
const testOut = (test.stdout || "") + (test.stderr || "");
const failMatch = testOut.match(/ℹ fail (\d+)/);
const testFailures = failMatch ? Number(failMatch[1]) : -1;
if (test.status !== 0 || testFailures !== 0) {
  red.push(`gates tests: ${testFailures >= 0 ? testFailures + " failing" : "did not run cleanly"}`);
}

// 2. GATES.md freshness: regenerate to a temp string and compare.
// The report script writes the file, so snapshot the committed copy first.
const gatesPath = join(repoRoot, "docs", "GATES.md");
const committed = existsSync(gatesPath) ? readFileSync(gatesPath, "utf-8") : "";
const regen = spawnSync(process.execPath, ["scripts/gates-report.mjs"], {
  cwd: repoRoot,
  encoding: "utf-8",
});
const fresh = existsSync(gatesPath) ? readFileSync(gatesPath, "utf-8") : "";
// The generated timestamp changes every run, so compare ignoring the
// Generated line.
const stripGenerated = (s) => s.replace(/^Generated .*$/m, "Generated <ts>");
if (stripGenerated(committed) !== stripGenerated(fresh)) {
  red.push("docs/GATES.md is stale — run `npm run gates:report` and commit it");
}
if (regen.status !== 0) red.push("gates:report did not run cleanly");
// The report prints RED when a gate is open; treat that as red here too.
if ((regen.stdout || "").includes(" — RED")) {
  red.push("gates:report says RED — a gate is open or bypassed");
}

if (red.length === 0) {
  console.log("gates: GREEN — every gate holds");
  process.exit(0);
} else {
  console.log("gates: RED");
  for (const r of red) console.log(`  - ${r}`);
  process.exit(1);
}
