/**
 * Feature registry guard: every LIVE feature in features.json must be
 * present at its route/endpoint. Removing or renaming a live feature
 * without updating the registry fails this test.
 */
import { describe, it } from "node:test";
import assert from "node:assert/strict";
import { existsSync, readFileSync, readdirSync } from "node:fs";
import { fileURLToPath } from "node:url";
import path from "node:path";
import { FOOTER_GROUPS, NAV, PUBLIC_SYSTEM_PATHS, SYSTEM_PATHWAYS } from "./hami-system.ts";

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

  it("every implemented top-level page route has an explicit registry lifecycle state", () => {
    const routeFiles = readdirSync(path.join(root, "routes")).filter((name) => name.endsWith(".tsx"));
    const routes = new Set<string>();
    for (const filename of routeFiles) {
      const base = filename.slice(0, -4);
      if (base === "__root" || base === "$") continue;
      const normalized = base.endsWith(".index") ? base.slice(0, -".index".length) : base;
      routes.add(base === "index" ? "/" : "/" + normalized.replace(/\./g, "/"));
    }
    const registered = new Set(registry.features.map((feature: { route: string }) => feature.route));
    const missing = [...routes].filter((route) => !registered.has(route));
    assert.deepEqual(missing, [], `route files missing a registry entry: ${missing.join(", ")}`);
  });

  it("all Hami navigation and pathway routes are registered as live", () => {
    const required = [
      ...NAV.map((item) => item.to),
      ...FOOTER_GROUPS.flatMap((group) => group.items.map((item) => item.to)),
      ...PUBLIC_SYSTEM_PATHS,
    ];
    const missing = [...new Set(required)].filter((route) =>
      !registry.features.some((feature: { route: string; status: string }) => feature.route === route && feature.status === "live"),
    );
    assert.deepEqual(missing, [], `public Hami pathways missing a live registry entry: ${missing.join(", ")}`);
  });

  it("every related Hami pathway points to a live registered route", () => {
    const targets = Object.values(SYSTEM_PATHWAYS).flatMap((links) => links.map((link) => link.to));
    const broken = [...new Set(targets)].filter(
      (route) => !registry.features.some((feature: { route: string; status: string }) => feature.route === route && feature.status === "live"),
    );
    assert.deepEqual(broken, [], `pathways pointing to missing or non-live registry routes: ${broken.join(", ")}`);
  });

  it("every page pathway uses a key in the canonical pathway map", () => {
    const routeDir = path.join(root, "routes");
    const keys = new Set(Object.keys(SYSTEM_PATHWAYS));
    const invalid: string[] = [];
    for (const filename of readdirSync(routeDir).filter((name) => name.endsWith(".tsx"))) {
      const source = readFileSync(path.join(routeDir, filename), "utf8");
      for (const match of source.matchAll(/HamiPathways current="([^"]+)"/g)) {
        if (!keys.has(match[1] as keyof typeof SYSTEM_PATHWAYS)) {
          invalid.push(`${filename}: ${match[1]}`);
        }
      }
    }
    assert.deepEqual(invalid, [], `pages use undefined Hami pathway keys: ${invalid.join(", ")}`);
  });

  it("the public sitemap contains only live Hami routes", () => {
    const sitemap = readFileSync(path.join(root, "..", "public", "sitemap.xml"), "utf8");
    const paths = [...sitemap.matchAll(/<loc>https:\/\/haminp\.vercel\.app([^<]*)<\/loc>/g)]
      .map((match) => match[1] || "/");
    assert.equal(new Set(paths).size, paths.length, "sitemap contains duplicate routes");
    const resolveFeature = (route: string) =>
      registry.features.find((feature: { route: string }) => feature.route === route) ??
      registry.features.find((feature: { route: string }) => {
        const pattern = feature.route.split("/");
        const candidate = route.split("/");
        return pattern.length === candidate.length &&
          pattern.every((segment, index) => segment.startsWith("$") ? candidate[index].length > 0 : segment === candidate[index]);
      });
    const inactive = paths.filter((route) => resolveFeature(route)?.status !== "live");
    assert.deepEqual(inactive, [], `sitemap lists hidden/archived/unregistered paths: ${inactive.join(", ")}`);
    assert.ok(!paths.includes("/contact"), "closed contact surface must not be presented as an active search destination");
  });

  it("owner-only, TEST-only and closed intake surfaces remain hidden", () => {
    const status = (route: string) => registry.features.find((feature: { route: string }) => feature.route === route)?.status;
    for (const route of ["/owner", "/operations", "/prototype/inbox", "/bot-qualification-demo", "/forge-bot-intake", "/request", "/contact"]) {
      assert.equal(status(route), "hidden", `${route} must stay out of public discovery`);
    }
    for (const route of ["/climb", "/what-we-learned", "/work", "/request-a-project"]) {
      assert.equal(status(route), "archived", `${route} should remain a compatibility redirect, not a parallel surface`);
    }
  });

  it("serves the schema referenced by the public feature registry", () => {
    const schemaPath = path.join(root, "..", "public", "features.schema.json");
    assert.ok(existsSync(schemaPath), "public/features.schema.json is missing");
    const schema = JSON.parse(readFileSync(schemaPath, "utf8"));
    assert.equal(registry.$schema, schema.$id);
    assert.equal(schema.$id, "https://haminp.vercel.app/features.schema.json");
    assert.equal(schema.$defs.feature.properties.status.enum.join(","), "live,hidden,archived,planned");
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
