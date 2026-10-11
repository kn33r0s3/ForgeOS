import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import test from "node:test";

const ROOT = join(dirname(fileURLToPath(import.meta.url)), "..");
const START = readFileSync(join(ROOT, "start.sh"), "utf8");
const COMPOSE = readFileSync(join(ROOT, "docker-compose.yml"), "utf8");
const WEB_DB = readFileSync(join(ROOT, "src/lib/db.ts"), "utf8");

test("Docker startup uses the canonical root Vite app, not archived Next.js", () => {
  assert.ok(START.includes("docker compose up --build -d"));
  assert.ok(START.includes("npm run dev"));
  assert.ok(!START.includes("exec docker compose"));
  assert.ok(COMPOSE.includes('frontend:\n    profiles: ["legacy-frontend"]'));
  assert.ok(COMPOSE.includes('caddy:\n    profiles: ["legacy-frontend"]'));
  assert.ok(COMPOSE.includes('127.0.0.1:3000:3000'));
});

test("the default backend SQLite URL is scoped away from the root web process", () => {
  assert.ok(START.includes('BACKEND_DATABASE_URL="${DATABASE_URL:-sqlite:///$PWD/storage/forge.db}"'));
  assert.ok(START.includes('export DATABASE_URL="$BACKEND_DATABASE_URL"'));
  assert.ok(!START.includes('export DATABASE_URL="${DATABASE_URL:-sqlite:///'));
  assert.ok(WEB_DB.includes('const dbSource: DbSource = databaseUrl ? "neon" : "pglite"'));
});

test("optional triage URLs never get invented local defaults", () => {
  assert.ok(COMPOSE.includes('EVIDENCE_TRIAGE_URL: ${EVIDENCE_TRIAGE_URL:-}'));
  assert.ok(COMPOSE.includes('X402_RESOURCE_URL: ${X402_RESOURCE_URL:-}'));
  assert.ok(COMPOSE.includes('profiles: ["paid-triage"]'));
});
