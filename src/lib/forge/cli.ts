#!/usr/bin/env node
/**
 * ForgeBot v1 — the runner.
 *
 * The operator no longer picks angles or gates findings by hand.
 * ForgeBot (the scheduled round worker) uses this CLI as its tools:
 *
 *   forge angles [--limit 5]   top value-ranked untried angles as JSON
 *   forge tried "<angle>"       1 if the angle was tried, 0 if new ground
 *   forge gate                 read findings JSON from stdin, print verdict JSON
 *
 * The worker researches the chosen angle, then gates its own findings
 * through verifyRound before banking. The operator grades the banked
 * round — competitor stage: ForgeBot does the work, musa checks it.
 *
 * Run: node --experimental-strip-types src/lib/forge/cli.ts <command>
 */
import { isAngleTried, ripenessQueue, verifyRound } from "./assistant.ts";

const [command, ...rest] = process.argv.slice(2);

function usage(): never {
  console.error("usage: cli.ts angles [--limit N] | tried \"<angle>\" | gate");
  process.exit(1);
}

if (command === "angles") {
  const limitIdx = rest.indexOf("--limit");
  const limit = limitIdx >= 0 ? parseInt(rest[limitIdx + 1] ?? "5", 10) : 5;
  const angles = ripenessQueue(70)
    .filter((a) => !isAngleTried(a.question))
    .slice(0, limit)
    .map((a) => ({
      id: a.id,
      question: a.question,
      valueTier: a.valueTier,
      valueWhy: a.valueWhy,
      cheapestTest: a.cheapestTest,
      ripeness: a.ripeness,
      round: a.round,
    }));
  console.log(JSON.stringify({ angles }, null, 2));
} else if (command === "tried") {
  const angle = rest.join(" ");
  if (!angle) usage();
  console.log(isAngleTried(angle) ? 1 : 0);
} else if (command === "gate") {
  let input = "";
  process.stdin.setEncoding("utf8");
  process.stdin.on("data", (c) => (input += c));
  process.stdin.on("end", () => {
    try {
      const findings = JSON.parse(input);
      if (!Array.isArray(findings)) throw new Error("expected a JSON array of findings");
      const verdict = verifyRound(findings);
      console.log(
        JSON.stringify(
          {
            verified: verdict.verified.map((f) => f.statement.slice(0, 120)),
            rejected: verdict.rejected.map((r) => ({
              statement: r.finding.statement.slice(0, 120),
              reason: r.reason,
            })),
          },
          null,
          2,
        ),
      );
      process.exit(verdict.rejected.length > 0 ? 2 : 0);
    } catch (e) {
      console.error(`gate failed: ${e instanceof Error ? e.message : e}`);
      process.exit(3);
    }
  });
} else {
  usage();
}
