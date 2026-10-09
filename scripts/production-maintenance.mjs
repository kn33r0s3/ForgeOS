import { appendFileSync, readFileSync } from "node:fs";
import path from "node:path";
import process from "node:process";
import { fileURLToPath, pathToFileURL } from "node:url";

export const PRODUCTION_DOMAINS = [
  "https://haminp.vercel.app",
  "https://forge-os-ebon.vercel.app",
];

const OWNER_READINESS_PATH = "/api/forge-bot/owner/readiness";
// The daily maintenance heartbeat has one missed-run grace period.
const MAX_HEARTBEAT_AGE_SECONDS = 48 * 60 * 60;
const root = path.dirname(path.dirname(fileURLToPath(import.meta.url)));

export function productionPageRoutes(features) {
  return features
    .filter(
      (feature) =>
        feature?.status === "live" &&
        typeof feature.route === "string" &&
        feature.route.startsWith("/") &&
        !feature.route.startsWith("/api") &&
        !feature.route.includes("$") &&
        !feature.route.includes("*"),
    )
    .map((feature) => feature.route);
}

export function evaluateIntakeConfig(config) {
  if (typeof config?.intake_enabled !== "boolean") {
    return ["intake_enabled is missing or invalid."];
  }
  return config.intake_enabled ? ["intake_enabled is true."] : [];
}

export function evaluateOwnerReadiness(
  readiness,
  maxHeartbeatAgeSeconds = MAX_HEARTBEAT_AGE_SECONDS,
) {
  const failures = [];
  if (readiness?.intake_enabled !== false) {
    failures.push("Owner readiness does not confirm intake_enabled=false.");
  }
  if (readiness?.live_enabled !== false) {
    failures.push("Owner readiness does not confirm live_enabled=false.");
  }
  const age = readiness?.last_maintenance_age_seconds;
  if (!Number.isFinite(age) || age < 0) {
    failures.push("Maintenance heartbeat age is unavailable.");
  } else if (age > maxHeartbeatAgeSeconds) {
    failures.push(
      `Maintenance heartbeat is stale (${Math.floor(age / 3600)} hours old; limit ${Math.floor(maxHeartbeatAgeSeconds / 3600)} hours).`,
    );
  }
  return failures;
}

async function get(fetchImpl, url, headers = {}) {
  return fetchImpl(url, {
    method: "GET",
    headers,
    redirect: "manual",
    signal: AbortSignal.timeout(15000),
  });
}

async function fetchJson(fetchImpl, url, headers = {}) {
  const response = await get(fetchImpl, url, headers);
  if (!response.ok) {
    return {
      response,
      json: null,
      failure: `GET ${url} returned HTTP ${response.status}.`,
    };
  }
  try {
    return { response, json: await response.json(), failure: null };
  } catch {
    return {
      response,
      json: null,
      failure: `GET ${url} returned invalid JSON.`,
    };
  }
}

export async function runPostDeploySmoke(
  fetchImpl = fetch,
  domains = PRODUCTION_DOMAINS,
) {
  const failures = [];
  for (const domain of domains) {
    for (const endpoint of ["/api/health", "/api/forge-bot/config"]) {
      const url = `${domain}${endpoint}`;
      try {
        const result = await fetchJson(fetchImpl, url);
        if (result.failure) {
          failures.push(result.failure);
        } else if (endpoint.endsWith("/config")) {
          failures.push(
            ...evaluateIntakeConfig(result.json).map(
              (failure) => `GET ${url}: ${failure}`,
            ),
          );
        }
      } catch (error) {
        failures.push(`GET ${url} failed (${error?.name ?? "request error"}).`);
      }
    }
  }
  return failures;
}

export function hasNoindexRobotsTag(html) {
  const tags = html.match(/<meta\b[^>]*>/gi) ?? [];
  return tags.some((tag) => {
    const name = tag.match(/\bname=["']([^"']+)["']/i)?.[1];
    const content = tag.match(/\bcontent=["']([^"']+)["']/i)?.[1];
    return name?.toLowerCase() === "robots" && /\bnoindex\b/i.test(content ?? "");
  });
}

function errorName(error) {
  return error && typeof error.name === "string" ? error.name : "request error";
}

export async function runNightlyChecks(
  fetchImpl = fetch,
  {
    domains = PRODUCTION_DOMAINS,
    apiKey = process.env.FORGE_API_KEY ?? "",
    features = JSON.parse(
      readFileSync(path.join(root, "features.json"), "utf8"),
    ).features,
  } = {},
) {
  const failures = await runPostDeploySmoke(fetchImpl, domains);
  const routes = productionPageRoutes(features);
  let heartbeatAgeSeconds = null;

  for (const domain of domains) {
    for (const route of routes) {
      const url = `${domain}${route}`;
      try {
        const response = await get(fetchImpl, url);
        if (response.status < 200 || response.status >= 400) {
          failures.push(`Read-only crawl GET ${url} returned HTTP ${response.status}.`);
          continue;
        }
        if (route === "/owner") {
          const html = await response.text();
          if (!hasNoindexRobotsTag(html)) {
            failures.push(`${url} does not contain a robots noindex meta tag.`);
          }
        }
      } catch (error) {
        failures.push(`Read-only crawl GET ${url} failed (${errorName(error)}).`);
      }
    }
  }

  if (!apiKey) {
    failures.push("Owner readiness check is blocked: FORGE_API_KEY is unavailable.");
  } else {
    const url = `${domains[0]}${OWNER_READINESS_PATH}`;
    try {
      const result = await fetchJson(fetchImpl, url, { "X-API-Key": apiKey });
      if (result.failure) {
        failures.push(result.failure);
      } else {
        const age = result.json?.last_maintenance_age_seconds;
        if (Number.isFinite(age) && age >= 0) heartbeatAgeSeconds = age;
        failures.push(...evaluateOwnerReadiness(result.json));
      }
    } catch (error) {
      failures.push(`GET owner readiness failed (${errorName(error)}).`);
    }
  }

  return {
    failures,
    crawledRouteCount: routes.length * domains.length,
    heartbeatAgeSeconds,
  };
}

function writeWorkflowSummary(result) {
  const heartbeatSummary =
    result.heartbeatAgeSeconds == null
      ? "Heartbeat age unavailable."
      : `Heartbeat age: ${Math.floor(result.heartbeatAgeSeconds / 3600)} hours.`;
  const summary = result.failures.length
    ? `${result.failures.length} production maintenance check(s) failed; ${result.crawledRouteCount} route reads attempted. ${heartbeatSummary}`
    : `All production maintenance checks passed; ${result.crawledRouteCount} route reads completed. ${heartbeatSummary}`;
  if (process.env.GITHUB_OUTPUT) {
    appendFileSync(process.env.GITHUB_OUTPUT, `summary=${summary}\n`);
  }
  if (process.env.GITHUB_STEP_SUMMARY) {
    appendFileSync(
      process.env.GITHUB_STEP_SUMMARY,
      `## Production maintenance checks\n\n${summary}\n\n${
        result.failures.length
          ? result.failures.map((failure) => `- ${failure}`).join("\n")
          : "Intake and LIVE were confirmed closed; no owner/private response data is included."
      }\n`,
    );
  }
  for (const failure of result.failures) console.error(failure);
  console.log(summary);
}

async function main() {
  const mode = process.argv[2];
  if (mode === "--smoke") {
    const failures = await runPostDeploySmoke();
    const result = {
      failures,
      crawledRouteCount: 0,
    };
    writeWorkflowSummary(result);
    if (failures.length) process.exitCode = 1;
    return;
  }
  if (mode !== "--nightly") {
    throw new Error("Expected --smoke or --nightly.");
  }
  const result = await runNightlyChecks();
  writeWorkflowSummary(result);
  if (result.failures.length) process.exitCode = 1;
}

if (
  process.argv[1] &&
  import.meta.url === pathToFileURL(path.resolve(process.argv[1])).href
) {
  main().catch((error) => {
    console.error(`Production maintenance check failed (${errorName(error)}).`);
    process.exitCode = 1;
  });
}
