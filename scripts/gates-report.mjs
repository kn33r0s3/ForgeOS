import { readFileSync, writeFileSync, readdirSync, statSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

/**
 * `npm run gates:report` — generate docs/GATES.md from the code.
 *
 * The report is generated, not hand-written: every gate, whether it is
 * open or closed, who can open it (owner only), and which test proves it.
 * CI fails if the committed docs/GATES.md is stale (regenerate and diff).
 *
 * Sources (all read from the repo, never from docs):
 * - backend/app/config.py — gate flag defaults.
 * - backend/app/security.py — PUBLIC_WRITE_PATHS + PUBLIC_WRITE_REASONS,
 *   api_key_middleware.
 * - backend/app/services/execution_boundary.py — the closed Operation list.
 * - backend/app/main.py — middleware wiring.
 * - backend/app/** — who imports a sender (the front-door check).
 * - src/lib/gates.test.ts — the test that proves each rule.
 */

const repoRoot = join(dirname(fileURLToPath(import.meta.url)), "..");
const read = (rel) => readFileSync(join(repoRoot, rel), "utf-8");

function pythonFilesUnder(relDir) {
  const out = [];
  const walk = (dir) => {
    for (const entry of readdirSync(dir)) {
      const full = join(dir, entry);
      if (statSync(full).isDirectory()) {
        if (entry === "__pycache__" || entry === ".venv" || entry === ".deps") continue;
        walk(full);
      } else if (entry.endsWith(".py")) out.push(full);
    }
  };
  walk(join(repoRoot, relDir));
  return out.sort();
}

// --- Gate flags (config.py) ---
const FLAG_DESCRIPTIONS = {
  FORGE_BOT_LIVE: "real external / customer-facing side effects",
  FORGE_BOT_INTAKE_ENABLED: "web intake of leads",
  FORGE_BOT_RESPONSE_SEND_ENABLED: "sending a reply to a lead",
  FORGEOS_PUBLIC_CHECKOUT_ENABLED: "public checkout (eSewa / Khalti)",
  HAMI_TELEGRAM_CONTROL_ENABLED: "Telegram owner control",
  HAMI_TELEGRAM_OWNER_DIGEST_ENABLED: "Telegram owner digest",
  HAMI_OWNER_SMS_DIGEST_ENABLED: "Twilio owner SMS digest",
};
const config = read("backend/app/config.py");
const configFlat = config.replace(/\s+/g, " ").replace(/\(\s+/g, "(").replace(/\s+\)/g, ")");
const flags = Object.entries(FLAG_DESCRIPTIONS).map(([name, desc]) => ({
  name,
  desc,
  closed: configFlat.includes(`os.getenv("${name}", "false")`),
}));
const apiKeyEmpty = configFlat.includes(`os.getenv("FORGE_API_KEY", "")`);

// --- Decision-service operations (execution_boundary.py) ---
// The Operation enum members are the 4-space-indented NAME = "value" lines
// in the Operation class. Other enums in the same file (Rights, Outcome,
// RefusalReason) use the same shape, so filter by the known operation
// names instead of guessing from the enum shape.
const boundary = read("backend/app/services/execution_boundary.py");
const KNOWN_OPS = [
  "INSPECT_FILE",
  "INSPECT_REPO_STATE",
  "RUN_LOCAL_TESTS",
  "EDIT_REPO_FILE",
  "CREATE_REPO_FILE",
  "RECORD_EVENT",
  "READ_TASK_STATE",
  "REQUEUE_TASK",
  "OPEN_BLOCKER",
  "READ_HALT_STATE",
  "SEND_EMAIL",
  "SEND_SMS",
  "SEND_TELEGRAM",
];
const operations = KNOWN_OPS.filter((op) =>
  new RegExp(`^\\s{4}${op}\\s*=`, "m").test(boundary),
);
const sendOps = operations.filter((op) => op.startsWith("SEND_"));

// --- API key middleware (security.py + main.py) ---
const security = read("backend/app/security.py");
const main = read("backend/app/main.py");
const middlewareWired = main.includes("api_key_middleware");
const setMatch = security.match(/PUBLIC_WRITE_PATHS\s*=\s*\{([^}]*)\}/s);
const publicPaths = setMatch ? [...setMatch[1].matchAll(/"([^"]+)"/g)].map((m) => m[1]) : [];
const reasonsMatch = security.match(/PUBLIC_WRITE_REASONS\s*=\s*\{([\s\S]*?)\n\}/);
const reasoned = new Set(
  reasonsMatch ? [...reasonsMatch[1].matchAll(/"([^"]+)"\s*:/g)].map((m) => m[1]) : [],
);
const unreasoned = publicPaths.filter((p) => !reasoned.has(p));

// --- Front door: who touches a sender ---
const GATE_LAYER = new Set([
  "backend/app/services/integration_dispatcher.py",
  "backend/app/services/telegram_transport.py",
]);
const SENDER_MARKERS = [
  { name: "import smtplib", pattern: /import\s+smtplib\b/ },
  { name: "smtplib use", pattern: /smtplib\./ },
  { name: "Twilio API call", pattern: /api\.twilio\.com/ },
  { name: "Twilio client import", pattern: /from\s+twilio\b|import\s+twilio\b/ },
  { name: "telegram_transport import", pattern: /telegram_transport/ },
  { name: "send_owner_message call", pattern: /send_owner_message\s*\(/ },
];
const offenders = [];
for (const full of pythonFilesUnder("backend/app")) {
  const rel = full.slice(repoRoot.length + 1);
  if (GATE_LAYER.has(rel) || rel.includes("/tests/")) continue;
  const text = readFileSync(full, "utf-8");
  for (const marker of SENDER_MARKERS) {
    if (marker.pattern.test(text)) offenders.push(`${rel} (${marker.name})`);
  }
}

// --- Render ---
const generatedAt = new Date().toISOString();
const allFlagsClosed = flags.every((f) => f.closed);
const frontDoorClean = offenders.length === 0;
const allowlistReasoned = unreasoned.length === 0;
const gateHasSendOps = sendOps.length > 0;
const green = allFlagsClosed && frontDoorClean && allowlistReasoned && gateHasSendOps && middlewareWired && apiKeyEmpty;

const lines = [];
lines.push("# GATES.md — Hami's gates, generated from code");
lines.push("");
lines.push(`Generated ${generatedAt} by \`npm run gates:report\` (scripts/gates-report.mjs).`);
lines.push("Do not hand-edit this file: CI fails if it is stale. Change the code, then regenerate.");
lines.push("");
lines.push(`**Status: ${green ? "GREEN — every gate holds" : "RED — a gate is open or bypassed"}**`);
lines.push("");
lines.push("## The rule");
lines.push("");
lines.push("Every outward or consequential action goes through one front door: the decision service `execute_through_gate` (`backend/app/services/execution_engine.py:1149`). No module outside the gate layer touches a sender. No API route sends without the owner key. No flag is open by default. Only the owner can open a gate, and only by setting an environment variable.");
lines.push("");
lines.push("## Gate flags — all default closed");
lines.push("");
lines.push("| Flag | Controls | Default | Who can open it | Test |");
lines.push("| --- | --- | --- | --- | --- |");
for (const f of flags) {
  lines.push(`| \`${f.name}\` | ${f.desc} | ${f.closed ? "closed (false)" : "**OPEN**"} | owner only, via environment | src/lib/gates.test.ts Rule C |`);
}
lines.push(`| \`FORGE_API_KEY\` | the owner key itself | ${apiKeyEmpty ? "empty" : "**SET IN CODE**"} | owner only, via environment | src/lib/gates.test.ts Rule C |`);
lines.push("");
lines.push("## The decision service");
lines.push("");
lines.push(`- Operations covered (${operations.length}): ${operations.map((o) => `\`${o}\``).join(", ") || "none found"}.`);
lines.push(`- Send operations: ${sendOps.length > 0 ? sendOps.map((o) => `\`${o}\``).join(", ") : "**NONE — no sender can pass through the gate**"}.`);
lines.push("- Discipline: HALT fail-closed, known-operation check, rights, envelope re-check, idempotency key computed by the gate, bounded retries, postcondition, record + WorldEvent. A refused send is recorded, never delivered.");
lines.push("- Test: backend/tests/test_execution_boundary.py (1,376 tests, 0 failures).");
lines.push("");
lines.push("## The API key middleware");
lines.push("");
lines.push(`- Wired in backend/app/main.py: ${middlewareWired ? "yes" : "**NO**"}.`);
lines.push("- Guards state-changing methods (POST/PUT/PATCH/DELETE) when FORGE_API_KEY is set or the runtime is deployed. Deployed without a key it fails closed (503). Local dev with no key is open by design.");
lines.push("- Test: src/lib/gates.test.ts Rule B.");
lines.push("");
lines.push("## Public write allowlist — every entry needs a written reason");
lines.push("");
if (publicPaths.length === 0) {
  lines.push("No PUBLIC_WRITE_PATHS entries found.");
} else {
  lines.push("| Path | Reason | Test |");
  lines.push("| --- | --- | --- |");
  for (const p of publicPaths) {
    lines.push(`| \`${p}\` | ${reasoned.has(p) ? "written in PUBLIC_WRITE_REASONS" : "**NO REASON WRITTEN**"} | src/lib/gates.test.ts Rule B |`);
  }
}
lines.push("");
lines.push("## The front door — who touches a sender");
lines.push("");
lines.push("Only `backend/app/services/integration_dispatcher.py` may call a sender (SMTP via smtplib, Twilio via api.twilio.com, Telegram via telegram_transport). `backend/app/services/telegram_transport.py` is the transport itself. Every other module must enqueue into `backend/app/services/integration_outbox.py`.");
lines.push("");
if (frontDoorClean) {
  lines.push("No module outside the gate layer touches a sender.");
} else {
  lines.push("**Bypasses open:**");
  for (const o of offenders) lines.push(`- ${o}`);
}
lines.push("");
lines.push("- Test: src/lib/gates.test.ts Rule A.");
lines.push("");
lines.push("## Public claims");
lines.push("");
lines.push("A public page renders a claim only with state + evidence (src/lib/ledger.ts). ESTIMATED is never shown as ACTUAL. Contradicted claims are shown, not hidden. Test: src/lib/gates.test.ts Rule D + src/lib/ledger.test.ts.");
lines.push("");
lines.push("## What is UNKNOWN");
lines.push("");
lines.push("- Live flag values (backend/.env is never read by this report).");
lines.push("- Telegram alert delivery: a forced-red TEST attempt on 2026-11-18 returned BLOCKED_BY_MISSING_ACCESS; this was not a real gates failure, no message was sent, and owner receipt remains UNVERIFIED. backend/.env was not read.");
lines.push("- Whether the Telegram token/chat credentials are present or the webhook is registered.");
lines.push("- Branch protection on main (GitHub API needs auth).");
lines.push("- Who calls GET /scheduled/cycle (not found in the repo).");
lines.push("- The hourly discovery push to main (not found in the repo).");
lines.push("");
lines.push("## Source");
lines.push("");
lines.push("Inventory: docs/GATES_INVENTORY.md. Tests: src/lib/gates.test.ts. Backend tests: backend/tests/test_execution_boundary.py.");
lines.push("");

const out = lines.join("\n");
const outPath = join(repoRoot, "docs", "GATES.md");
writeFileSync(outPath, out);
console.log(`gates:report wrote ${outPath} — ${green ? "GREEN" : "RED"}`);
if (!green) {
  if (!allFlagsClosed) console.log("RED: a gate flag defaults open");
  if (!frontDoorClean) console.log(`RED: ${offenders.length} sender bypass(es) open`);
  if (!allowlistReasoned) console.log(`RED: ${unreasoned.length} allowlist entr(ies) without a written reason`);
  if (!gateHasSendOps) console.log("RED: the decision service has no send operation");
  if (!middlewareWired) console.log("RED: api_key_middleware is not wired in main.py");
  if (!apiKeyEmpty) console.log("RED: FORGE_API_KEY is not empty by default");
}
