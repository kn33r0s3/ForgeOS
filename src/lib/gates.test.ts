import assert from "node:assert/strict";
import { describe, it } from "node:test";
import { readFileSync, readdirSync, statSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { CLAIMS, canRender } from "./ledger.ts";

/**
 * Gates bypass tests. Each rule fails loudly naming the file and the rule.
 * These run in `npm test` (the src/lib test files).
 *
 * Rule A — only the gate layer touches a sender. The gate layer is
 * `integration_dispatcher.py` (the only module that may import smtplib,
 * call api.twilio.com, or import telegram_transport) and `telegram_transport.py`
 * (the transport itself). Every other module must reach a sender only by
 * enqueueing into `integration_outbox.py`. A direct sender call anywhere else
 * is a bypass.
 *
 * Rule B — every API route is behind the gate wrapper or an allowlist entry
 * with a written reason. The gate wrapper is the global `api_key_middleware`
 * wired in `backend/app/main.py`. The allowlist is `PUBLIC_WRITE_PATHS` in
 * `backend/app/security.py`, and every entry must have a reason in
 * `PUBLIC_WRITE_REASONS` next to it.
 *
 * Rule C — no gate flag is open by default. Every flag in
 * `backend/app/config.py` must default to "false" (or "" for a key).
 *
 * Rule D — a public page renders a claim only with state + evidence. Every
 * claim in the public ledger (`./ledger.ts`) must pass the ledger gate.
 *
 * Known outbound clients NOT covered by Rule A (service-to-service, not
 * senders to real people): `evidence_triage.py` (httpx to the internal
 * evidence-triage service) and the collectors in `services/collectors/`
 * (outbound HTTP that FETCHES data, it does not send to a person). If one of
 * those starts sending to a real person, it belongs under Rule A.
 */

const repoRoot = join(dirname(fileURLToPath(import.meta.url)), "..", "..");

function readRepo(relative: string): string {
  return readFileSync(join(repoRoot, relative), "utf-8");
}

function pythonFilesUnder(relativeDir: string): string[] {
  const out: string[] = [];
  const walk = (dir: string) => {
    for (const entry of readdirSync(dir)) {
      const full = join(dir, entry);
      if (statSync(full).isDirectory()) {
        if (entry === "__pycache__" || entry === ".venv" || entry === ".deps") continue;
        walk(full);
      } else if (entry.endsWith(".py")) {
        out.push(full);
      }
    }
  };
  walk(join(repoRoot, relativeDir));
  return out.sort();
}

/** The only modules allowed to touch a sender directly. */
const GATE_LAYER = new Set([
  "backend/app/services/integration_dispatcher.py",
  "backend/app/services/telegram_transport.py",
]);

/** Sender markers. A match outside the gate layer is a bypass. */
const SENDER_MARKERS: Array<{ name: string; pattern: RegExp }> = [
  { name: "import smtplib", pattern: /import\s+smtplib\b/ },
  { name: "smtplib use", pattern: /smtplib\./ },
  { name: "Twilio API call", pattern: /api\.twilio\.com/ },
  { name: "Twilio client import", pattern: /from\s+twilio\b|import\s+twilio\b/ },
  { name: "telegram_transport import", pattern: /telegram_transport/ },
  { name: "send_owner_message call", pattern: /send_owner_message\s*\(/ },
];

describe("gates bypass — Rule A: only the gate layer touches a sender", () => {
  it("no module outside the gate layer imports or calls a sender", () => {
    const offenders: string[] = [];
    for (const full of pythonFilesUnder("backend/app")) {
      const relative = full.slice(repoRoot.length + 1);
      if (GATE_LAYER.has(relative)) continue;
      if (relative.includes("/tests/")) continue;
      const text = readFileSync(full, "utf-8");
      for (const marker of SENDER_MARKERS) {
        if (marker.pattern.test(text)) {
          offenders.push(
            `GATE-BYPASS-A: ${relative} matches "${marker.name}" outside the gate layer`,
          );
        }
      }
    }
    assert.deepEqual(offenders, [], offenders.join("\n"));
  });

  it("the dispatcher is the only sender consumer", () => {
    const dispatcher = readRepo("backend/app/services/integration_dispatcher.py");
    assert.match(dispatcher, /import smtplib/, "dispatcher must own SMTP");
    assert.match(dispatcher, /api\.twilio\.com/, "dispatcher must own Twilio");
    assert.match(dispatcher, /telegram_transport/, "dispatcher must own Telegram");
  });
});

describe("gates bypass — Rule B: every route is gated or allowlisted with a reason", () => {
  it("the API key middleware is wired in main.py", () => {
    const main = readRepo("backend/app/main.py");
    assert.match(
      main,
      /api_key_middleware/,
      "GATE-BYPASS-B: backend/app/main.py does not wire api_key_middleware",
    );
  });

  it("every PUBLIC_WRITE_PATHS entry has a written reason", () => {
    const security = readRepo("backend/app/security.py");
    const setMatch = security.match(/PUBLIC_WRITE_PATHS\s*=\s*\{([^}]*)\}/s);
    assert.ok(setMatch, "GATE-BYPASS-B: PUBLIC_WRITE_PATHS not found in backend/app/security.py");
    const paths = [...setMatch[1].matchAll(/"([^"]+)"/g)].map((m) => m[1]);
    assert.ok(paths.length > 0, "GATE-BYPASS-B: PUBLIC_WRITE_PATHS is empty");
    const reasonsMatch = security.match(/PUBLIC_WRITE_REASONS\s*=\s*\{([\s\S]*?)\n\}/);
    assert.ok(
      reasonsMatch,
      "GATE-BYPASS-B: PUBLIC_WRITE_REASONS not found in backend/app/security.py — every allowlist entry needs a written reason",
    );
    const reasoned = new Set(
      [...reasonsMatch[1].matchAll(/"([^"]+)"\s*:/g)].map((m) => m[1]),
    );
    const missing = paths.filter((p) => !reasoned.has(p));
    assert.deepEqual(
      missing,
      [],
      `GATE-BYPASS-B: PUBLIC_WRITE_PATHS entries without a written reason: ${missing.join(", ")}`,
    );
  });
});

describe("gates bypass — Rule C: no gate flag is open by default", () => {
  const FLAGS = [
    "FORGE_BOT_LIVE",
    "FORGE_BOT_INTAKE_ENABLED",
    "FORGE_BOT_RESPONSE_SEND_ENABLED",
    "FORGEOS_PUBLIC_CHECKOUT_ENABLED",
    "HAMI_TELEGRAM_CONTROL_ENABLED",
    "HAMI_TELEGRAM_OWNER_DIGEST_ENABLED",
    "HAMI_OWNER_SMS_DIGEST_ENABLED",
  ];

  // Collapse all whitespace (the getenv calls span lines) and strip the
  // space a line break leaves after "(" / before ")", then plain
  // string-search for the default. No regex escaping to get wrong.
  const configFlat = readRepo("backend/app/config.py")
    .replace(/\s+/g, " ")
    .replace(/\(\s+/g, "(")
    .replace(/\s+\)/g, ")");

  for (const flag of FLAGS) {
    it(`${flag} defaults to closed`, () => {
      assert.ok(
        configFlat.includes(`os.getenv("${flag}", "false")`),
        `GATE-BYPASS-C: ${flag} does not default to "false" in backend/app/config.py`,
      );
    });
  }

  it("FORGE_API_KEY defaults to empty", () => {
    assert.ok(
      configFlat.includes(`os.getenv("FORGE_API_KEY", "")`),
      'GATE-BYPASS-C: FORGE_API_KEY does not default to "" in backend/app/config.py',
    );
  });
});

describe("gates bypass — Rule D: a public claim renders only with state + evidence", () => {
  it("every public ledger claim passes the ledger gate", () => {
    for (const claim of CLAIMS) {
      assert.equal(
        canRender(claim),
        true,
        `GATE-BYPASS-D: public claim ${claim.id} renders without state + evidence`,
      );
    }
  });

  it("at least one contradicted claim is shown, not hidden", () => {
    const contradicted = CLAIMS.filter((c) => c.state === "contradicted");
    assert.ok(contradicted.length >= 1, "GATE-BYPASS-D: no contradicted claim is shown");
    for (const claim of contradicted) {
      assert.ok(claim.contradictedBy, `GATE-BYPASS-D: ${claim.id} is contradicted but names nothing`);
    }
  });
});
