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
  assert.doesNotMatch(JSON.stringify(manifest), /grok|app-builder/i);
});

test("production shell has no Grok PWA injector or preview bridge", () => {
  const vite = readFileSync(join(ROOT, "vite.config.ts"), "utf8");
  const root = readFileSync(join(ROOT, "src/routes/__root.tsx"), "utf8");
  assert.doesNotMatch(vite, /grokPwaPlugin|grok-pwa-plugin|grok-pwa\\.ts/);
  assert.doesNotMatch(root, /PreviewHostBridge|__grok\\//);
  assert.match(root, /\\/manifest\\.webmanifest/);
  assert.equal(existsSync(join(ROOT, "server/middleware/grok-pwa.ts")), false);
  assert.equal(existsSync(join(ROOT, "scripts/grok-pwa-plugin.mjs")), false);
});

test("connector errors do not instruct Hami visitors to use another app", () => {
  const errors = readFileSync(join(ROOT, "src/lib/app-data/errors.ts"), "utf8");
  assert.doesNotMatch(errors, /Grok|grok\\.me|edge gate|open this app/i);
  assert.match(errors, /isn’t available on this site yet/);
  assert.match(errors, /isn’t configured yet/);
});
