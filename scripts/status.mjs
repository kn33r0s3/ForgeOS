#!/usr/bin/env node
/**
 * npm run status — plain-English project status.
 * Prints: live features, hidden/archived features, last 10 commits,
 * failing tests, and deployed bundle vs local HEAD.
 */
import { execSync } from "node:child_process";
import { readFileSync, readdirSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const root = path.dirname(path.dirname(fileURLToPath(import.meta.url)));
const sh = (cmd) => execSync(cmd, { cwd: root, encoding: "utf8" }).trim();

console.log("=== HAMI STATUS ===\n");

// Features
const registry = JSON.parse(readFileSync(path.join(root, "features.json"), "utf8"));
const live = registry.features.filter((f) => f.status === "live");
const nonLive = registry.features.filter((f) => f.status !== "live");
console.log(`Live features (${live.length}):`);
for (const f of live) console.log(`  - ${f.name} (${f.route})`);
console.log(`\nHidden/archived/planned features (${nonLive.length}):`);
for (const f of nonLive) console.log(`  - ${f.name} (${f.route}) [${f.status}]`);

// Commits
console.log("\nLast 10 commits:");
console.log(sh("git log --oneline -10").split("\n").map((l) => `  ${l}`).join("\n"));

// Tests (frontend; backend suite is slow — run separately)
console.log("\nFrontend tests:");
try {
  const out = execSync("npm test 2>&1", { cwd: root, encoding: "utf8", timeout: 120000 });
  const fails = (out.match(/fail (\d+)/g) || []).map((m) => Number(m.split(" ")[1]));
  const totalFail = fails.reduce((a, b) => a + b, 0);
  console.log(totalFail === 0 ? "  All passing." : `  FAILING: ${totalFail} tests failing.`);
} catch {
  console.log("  Could not run tests (see output above).");
}

// Deployed bundle vs HEAD
console.log("\nDeployment:");
const head = sh("git rev-parse --short HEAD");
console.log(`  Local HEAD: ${head}`);
try {
  const candidates = [
    path.join(root, ".vercel", "output", "static", "assets"),
    path.join(root, "dist", "assets"),
  ];
  const assetsDir = candidates.find((d) => {
    try { return readdirSync(d).length > 0; } catch { return false; }
  });
  const distFiles = assetsDir ? readdirSync(assetsDir).filter((f) => f.endsWith(".js")) : [];
  const localBundle = distFiles.find((f) => f.startsWith("index-")) ?? distFiles[0];
  const html = await (await fetch("https://haminp.vercel.app/?cb=" + Date.now())).text();
  const m = html.match(/assets\/(index-[^"]+\.js)/);
  if (m && localBundle) {
    if (m[1] === localBundle) console.log(`  Production serves the current build (${m[1]}).`);
    else console.log(`  MISMATCH: production serves ${m[1]}, local build is ${localBundle}. Deploy may be pending.`);
  } else {
    console.log("  Could not compare bundles (build or fetch failed).");
  }
} catch {
  console.log("  Could not reach production.");
}
console.log("\nDone.");
