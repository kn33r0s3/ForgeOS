import assert from "node:assert/strict";
import { existsSync, readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import test from "node:test";

const ROOT = join(dirname(fileURLToPath(import.meta.url)), "..");

test("Hami owns the production web-app manifest", () => {
  const manifest = JSON.parse(readFileSync(join(ROOT, "public/manifest.webmanifest"), "utf8"));
  assert.equal(manifest.name, "Hami");
  assert.equal(manifest.short_name, "Hami");
  assert.equal(manifest.start_url, "/");
  assert.equal(manifest.scope, "/");
  assert.equal(manifest.display, "standalone");
  assert.equal(manifest.icons[0].src, "/favicon.svg");
  assert.ok(!/grok|app-builder/i.test(JSON.stringify(manifest)));
});

test("production shell has no Grok PWA injector or preview bridge", () => {
  const vite = readFileSync(join(ROOT, "vite.config.ts"), "utf8");
  const root = readFileSync(join(ROOT, "src/routes/__root.tsx"), "utf8");
  assert.ok(!vite.includes("grokPwaPlugin"));
  assert.ok(!vite.includes("grok-pwa-plugin"));
  assert.ok(!root.includes("PreviewHostBridge"));
  assert.ok(!root.includes("/__grok/"));
  assert.ok(root.includes("/manifest.webmanifest"));
  assert.equal(existsSync(join(ROOT, "server/middleware/grok-pwa.ts")), false);
  assert.equal(existsSync(join(ROOT, "scripts/grok-pwa-plugin.mjs")), false);
});

test("connector errors do not instruct Hami visitors to use another app", () => {
  const errors = readFileSync(join(ROOT, "src/lib/app-data/errors.ts"), "utf8");
  assert.ok(!errors.includes("Grok"));
  assert.ok(!errors.toLowerCase().includes("grok.me"));
  assert.ok(!errors.toLowerCase().includes("edge gate"));
  assert.ok(!errors.toLowerCase().includes("open this app"));
  assert.ok(errors.includes("isn’t available on this site yet"));
  assert.ok(errors.includes("isn’t configured yet"));
});
