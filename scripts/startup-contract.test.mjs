import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import test from "node:test";

const ROOT = join(dirname(fileURLToPath(import.meta.url)), "..");
const START = readFileSync(join(ROOT, "start.sh"), "utf8");
const COMPOSE = readFileSync(join(ROOT, "docker-compose.yml"), "utf8");
const BACKEND_DOCKERFILE = readFileSync(join(ROOT, "backend/Dockerfile"), "utf8");
const WEB_DB = readFileSync(join(ROOT, "src/lib/db.ts"), "utf8");
const CHECK_ALL = readFileSync(join(ROOT, "scripts/check_all.sh"), "utf8");

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
  assert.ok(WEB_DB.includes('import { isWorkspacePreview } from "./env.server";'));
  assert.ok(
    WEB_DB.includes(
      'export const dbSource: DbSource = databaseUrl\n  ? "neon"\n  : isWorkspacePreview()\n    ? "pglite"\n    : "unavailable";',
    ),
  );
  assert.ok(
    WEB_DB.includes("DATABASE_URL must be configured for deployed database access"),
  );
});

test("Compose inherits the backend image healthcheck", () => {
  const backendBlock = COMPOSE.split("  backend:\n")[1]?.split("\n  worker:\n")[0] ?? "";
  assert.ok(!backendBlock.includes("healthcheck:"), "Compose must not override the image's Python healthcheck");
  assert.match(BACKEND_DOCKERFILE, /HEALTHCHECK[\s\S]*CMD \["python", "-c",/);
});

test("optional triage URLs never get invented local defaults", () => {
  assert.ok(COMPOSE.includes('EVIDENCE_TRIAGE_URL: ${EVIDENCE_TRIAGE_URL:-}'));
  assert.ok(COMPOSE.includes('X402_RESOURCE_URL: ${X402_RESOURCE_URL:-}'));
  assert.ok(COMPOSE.includes('profiles: ["paid-triage"]'));
});


test("the advertised check script is portable and uses repository-local dependency paths", () => {
  assert.ok(!CHECK_ALL.includes("/home/hatch/workspace/repos/ForgeOS"));
  assert.ok(CHECK_ALL.includes('PYTHONPATH="${DEPS:+$DEPS:}$PWD${PYTHONPATH:+:$PYTHONPATH}"'));
  assert.ok(CHECK_ALL.includes(".venv/bin/python"));
  assert.ok(CHECK_ALL.includes("venv/bin/python"));
});

test("the optional LiveKit smoke profile is loopback-only and publisher-scalable", () => {
  const publisherBlock =
    COMPOSE.split("  livekit-publisher:\n")[1]?.split("\n  livekit-load-test:\n")[0] ?? "";
  const loadTestBlock =
    COMPOSE.split("  livekit-load-test:\n")[1] ?? "";

  assert.ok(COMPOSE.includes('livekit:\n    profiles: ["livekit-local"]'));
  assert.ok(COMPOSE.includes("image: livekit/livekit-server:v1.13.11"));
  assert.ok(COMPOSE.includes('127.0.0.1:7880:7880/tcp'));
  assert.ok(COMPOSE.includes('127.0.0.1:7881:7881/tcp'));
  assert.ok(COMPOSE.includes('127.0.0.1:7882:7882/udp'));
  assert.ok(publisherBlock.includes('profiles: ["livekit-local"]'));
  assert.ok(publisherBlock.includes("image: livekit/livekit-cli:v2.19.4"));
  assert.ok(!publisherBlock.includes("container_name:"), "scaled publishers must not have a fixed container name");
  assert.ok(publisherBlock.includes("ws://livekit:7880"));
  assert.ok(publisherBlock.includes("--publish-demo"));
  assert.ok(publisherBlock.includes("hami-proving-ground"));
  assert.ok(loadTestBlock.includes("load-test"));
  assert.ok(loadTestBlock.includes("--subscribers"));
  assert.ok(loadTestBlock.includes("${LIVEKIT_TEST_SUBSCRIBERS:-25}"));
  assert.ok(loadTestBlock.includes("30s"));
  assert.ok(loadTestBlock.includes('"${LIVEKIT_TEST_LAYOUT:-speaker}"'));
});
