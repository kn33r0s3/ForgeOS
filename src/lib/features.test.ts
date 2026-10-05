/**
 * Feature registry guard: every LIVE feature in features.json must be
 * present at its route/endpoint. Removing or renaming a live feature
 * without updating the registry fails this test.
 */
import { describe, it } from "node:test";
import assert from "node:assert/strict";
import { existsSync, readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import path from "node:path";

const root = path.dirname(path.dirname(fileURLToPath(import.meta.url)));
const registry = JSON.parse(
  readFileSync(path.join(root, "..", "features.json"), "utf8"),
);

function routeFile(route: string): string {
  // "/" -> index.tsx, "/prototype/inbox" -> prototype.inbox.tsx
  const name = route === "/" ? "index" : route.slice(1).replace(/\//g, ".");
  return path.join(root, "routes", `${name}.tsx`);
}

describe("feature registry", () => {
  it("every live page feature has its route file", () => {
    const missing: string[] = [];
    for (const f of registry.features) {
      if (f.status !== "live" || !f.route || f.route.startsWith("/api")) continue;
      if (!existsSync(routeFile(f.route))) missing.push(`${f.id} -> ${f.route}`);
    }
    assert.deepEqual(missing, [], `live features missing route files: ${missing.join(", ")}`);
  });

  it("every live API feature has its endpoint registered in the backend", () => {
    const backend = readFileSync(
      path.join(root, "..", "backend", "app", "main.py"),
      "utf8",
    );
    const apiIndex = readFileSync(
      path.join(root, "..", "backend", "app", "api", "__init__.py"),
      "utf8",
    );
    // Public router prefixes live in their own modules.
    let haystack = backend + apiIndex;
    for (const f of registry.features) {
      if (f.status !== "live" || !f.endpoint || !f.endpoint.includes("/public")) continue;
      haystack += readFileSync(
        path.join(root, "..", "backend", "app", "api", "public.py"),
        "utf8",
      );
      break;
    }
    const missing: string[] = [];
    for (const f of registry.features) {
      if (f.status !== "live" || !f.endpoint) continue;
      // endpoint like "GET /api/health" -> Vercel routes /api/* to FastAPI,
      // so check the path after the /api prefix is registered.
      const endpointPath =
        f.endpoint.split(" ").pop().replace(/^\/api/, "").replace(/\/\*$/, "") || "/";
      if (!haystack.includes(`"${endpointPath}"`) && !haystack.includes(`'${endpointPath}'`)) {
        missing.push(`${f.id} -> ${f.endpoint}`);
      }
    }
    assert.deepEqual(missing, [], `live APIs missing endpoints: ${missing.join(", ")}`);
  });

  it("registry entries are well-formed", () => {
    for (const f of registry.features) {
      assert.ok(f.id && f.name && f.intent && f.route, `feature missing fields: ${JSON.stringify(f)}`);
      assert.match(f.status, /^(live|hidden|archived|planned)$/, `bad status on ${f.id}`);
      assert.ok(f.date_added && f.commit, `missing provenance on ${f.id}`);
    }
    const ids = registry.features.map((f: { id: string }) => f.id);
    assert.equal(new Set(ids).size, ids.length, "duplicate feature ids");
  });
});
