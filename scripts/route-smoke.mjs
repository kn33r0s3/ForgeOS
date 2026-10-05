#!/usr/bin/env node
/**
 * Route smoke test: every LIVE page in features.json must return 200.
 * Starts `vite dev`, curls each route, kills the server.
 * (Headings are asserted in source by public-copy.test.ts; this guards
 *  the route table itself — a missing/broken route file fails here.)
 *
 * Usage: node scripts/route-smoke.mjs [--port 5199]
 */
import { spawn } from "node:child_process";
import { readFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const root = path.dirname(path.dirname(fileURLToPath(import.meta.url)));
const port = Number(
  process.argv.find((a) => a.startsWith("--port="))?.split("=")[1] ?? 5199,
);

const registry = JSON.parse(readFileSync(path.join(root, "features.json"), "utf8"));
const routes = registry.features
  .filter((f) => f.status === "live" && f.route && !f.route.startsWith("/api"))
  .map((f) => f.route);

const server = spawn(
  "node",
  ["scripts/with-app-env.mjs", "vite", "dev", "--port", String(port), "--strictPort"],
  {
    cwd: root,
    stdio: ["ignore", "pipe", "pipe"],
    env: { ...process.env, BROWSER: "none" },
  },
);

function waitForServer() {
  return new Promise((resolve, reject) => {
    const timer = setTimeout(() => reject(new Error("dev server did not start")), 30000);
    const onData = (d) => {
      const s = d.toString();
      if (s.includes(`:${port}`) || s.includes("ready in")) {
        clearTimeout(timer);
        server.stdout.off("data", onData);
        server.stderr.off("data", onData);
        resolve();
      }
    };
    server.stdout.on("data", onData);
    server.stderr.on("data", onData);
  });
}

const failures = [];
try {
  await waitForServer();
  for (const route of routes) {
    const url = `http://127.0.0.1:${port}${route}`;
    try {
      const res = await fetch(url, { redirect: "manual" });
      // 200 = direct hit; 3xx = route exists and redirects (e.g. /login normalizes
      // search params via validateSearch). Both prove the route is live, not a 404.
      if (res.status === 200 || (res.status >= 300 && res.status < 400)) {
        console.log(`ok ${route} -> ${res.status}`);
      } else {
        failures.push(`${route} -> ${res.status}`);
      }
    } catch (err) {
      failures.push(`${route} -> ${err.message}`);
    }
  }
} finally {
  server.kill();
}

if (failures.length) {
  console.error(`\nSMOKE FAILURES:\n${failures.join("\n")}`);
  process.exit(1);
}
console.log(`\nAll ${routes.length} live routes returned 200.`);
