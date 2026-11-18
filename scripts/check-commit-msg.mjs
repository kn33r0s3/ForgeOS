import { readFileSync } from "node:fs";
import { execSync } from "node:child_process";

/**
 * Commit-message check — the rule for every Hami commit.
 *
 * Format: `[agent][task-id][gates touched or none] <one plain-English line>`
 * - agent: who did it (copilot, muse, nyx, niroj, chatgpt, codex, or unknown).
 * - task-id: the queue task (e.g. 007) or `none`.
 * - gates: which gates the change touches (e.g. `gates-front-door`, `gates-tests`)
 *   or `none`.
 *
 * Used two ways:
 * - As the commit-msg hook (.git/hooks/commit-msg calls it with the message
 *   file). A bad message is rejected before the commit lands.
 * - As the CI check (`node scripts/check-commit-msg.mjs <sha>...` or
 *   `--range <base>..<head>`). CI fails on any bad message in the range.
 *
 * Unknowable history is marked UNKNOWN in WHO_DID_WHAT.md, never guessed.
 */

export const COMMIT_MSG_PATTERN =
  /^\[([a-z][a-z0-9-]*)\]\[([a-z0-9-]+)\]\[([a-z0-9-, ]+)\]\s+(\S.*)$/;

export function checkCommitMessage(message) {
  const firstLine = message.split("\n")[0].trim();
  const m = COMMIT_MSG_PATTERN.exec(firstLine);
  if (!m) {
    return {
      ok: false,
      reason:
        `commit message must start with [agent][task-id][gates touched or none] — got: "${firstLine}"`,
    };
  }
  const [, agent, taskId, gates] = m;
  return { ok: true, agent, taskId, gates: gates.trim() };
}

const args = process.argv.slice(2);
if (args[0] === "--range" && args[1]) {
  // Range mode (CI): validate every commit subject in <base>..<head>.
  const range = args[1];
  let subjects;
  try {
    subjects = execSync(`git log --format="%H %s" ${range}`, { encoding: "utf-8" })
      .split("\n")
      .map((l) => l.trim())
      .filter(Boolean);
  } catch {
    console.error(`check-commit-msg: cannot read git log for range ${range}`);
    process.exit(1);
  }
  if (subjects.length === 0) {
    console.log(`check-commit-msg: no commits in range ${range}`);
    process.exit(0);
  }
  let bad = 0;
  for (const line of subjects) {
    const sp = line.indexOf(" ");
    const hash = sp >= 0 ? line.slice(0, sp).slice(0, 7) : line.slice(0, 7);
    const subject = sp >= 0 ? line.slice(sp + 1) : line;
    const result = checkCommitMessage(subject);
    if (!result.ok) {
      bad += 1;
      console.error(`check-commit-msg: ${hash} ${result.reason}`);
    }
  }
  if (bad > 0) {
    console.error(`check-commit-msg: ${bad} of ${subjects.length} commit(s) lack the [agent][task-id][gates] prefix`);
    process.exit(1);
  }
  console.log(`check-commit-msg: ${subjects.length} commit(s) in range ${range} all carry [agent][task-id][gates]`);
  process.exit(0);
}
if (args.length > 0 && !args[0].startsWith("--")) {
  // File mode (commit-msg hook): the first arg is the message file.
  const message = readFileSync(args[0], "utf-8");
  const result = checkCommitMessage(message);
  if (!result.ok) {
    console.error(`commit-msg: ${result.reason}`);
    console.error("commit-msg: format is [agent][task-id][gates touched or none] <summary>");
    process.exit(1);
  }
  process.exit(0);
}
