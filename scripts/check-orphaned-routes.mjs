/**
 * Orphaned route monitor — fails CI if any public indexed route has zero
 * inbound links from nav, footer, or homepage.
 *
 * Owner rule: "everything is used, nothing separation." An indexed-but-orphaned
 * route is invisible to users but visible to search engines — the worst combination.
 *
 * Intentionally excluded:
 * - /owner (owner-only, must stay unlinked)
 * - Redirect-only routes (e.g. /work → /domain)
 * - Routes with noindex (deliberately hidden from search)
 */

import { readFileSync, readdirSync } from "node:fs";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";

const root = join(dirname(fileURLToPath(import.meta.url)), "..");
const routesDir = join(root, "src/routes");

// Routes that are intentionally not linked
const INTENTIONALLY_UNLINKED = new Set([
  "/owner", // owner-only console
  "/operations", // internal engine dashboard; X-Robots-Tag noindex in vercel.json
]);

function getRoutePath(filename) {
  // Convert filename to route path: "about.tsx" → "/about", "group.businesses.tsx" → "/group/businesses"
  // Index routes: "group.index.tsx" → "/group", "services.index.tsx" → "/services"
  const base = filename.replace(/\.tsx$/, "");
  if (base === "index") return "/";
  if (base === "__root") return null; // layout, not a route
  if (base === "$") return null; // catch-all, not a page
  if (base.includes("$")) return null; // dynamic route, linked programmatically
  // Strip trailing .index → parent path
  const path = base.endsWith(".index") ? base.slice(0, -".index".length) : base;
  return "/" + path.replace(/\./g, "/");
}

function isRedirectOnly(content) {
  return /beforeLoad[\s\S]*?redirect/.test(content);
}

function hasNoindex(content) {
  return /noindex/.test(content);
}

function findInboundLinks(routePath, allFiles) {
  // Check nav, footer, homepage, and other routes for links to this path
  const pattern = new RegExp(`to=["']${routePath}["']|"\\${routePath}"`, "g");
  let count = 0;
  for (const { path, content } of allFiles) {
    // Don't count self-references
    if (path.includes(`routes/${routePath.slice(1).replace(/\//g, ".")}`)) continue;
    const matches = content.match(pattern);
    if (matches) count += matches.length;
  }
  return count;
}

function main() {
  const routeFiles = readdirSync(routesDir).filter((f) => f.endsWith(".tsx"));

  // Collect all source files for link scanning
  const allFiles = [];
  const collectFiles = (dir) => {
    for (const entry of readdirSync(dir, { withFileTypes: true })) {
      const full = join(dir, entry.name);
      if (entry.isDirectory()) {
        collectFiles(full);
      } else if (entry.name.endsWith(".tsx") || entry.name.endsWith(".ts")) {
        allFiles.push({ path: full, content: readFileSync(full, "utf8") });
      }
    }
  };
  collectFiles(join(root, "src"));

  const orphans = [];

  for (const filename of routeFiles) {
    const routePath = getRoutePath(filename);
    if (!routePath) continue;
    if (INTENTIONALLY_UNLINKED.has(routePath)) continue;

    const content = readFileSync(join(routesDir, filename), "utf8");
    if (isRedirectOnly(content)) continue;
    if (hasNoindex(content)) continue;

    // "/" is always reachable
    if (routePath === "/") continue;

    const inbound = findInboundLinks(routePath, allFiles);
    if (inbound === 0) {
      orphans.push(routePath);
    }
  }

  if (orphans.length > 0) {
    console.error("ORPHANED ROUTES (indexed but not linked from anywhere):");
    for (const r of orphans) console.error(`  ${r}`);
    console.error("\nFix: link from nav, footer, or homepage — or add noindex if intentionally hidden.");
    process.exit(1);
  }

  console.log(`OK: all ${routeFiles.length} routes are connected or intentionally hidden.`);
}

main();
