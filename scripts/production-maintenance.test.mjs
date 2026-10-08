import assert from "node:assert/strict";
import test from "node:test";
import {
  evaluateIntakeConfig,
  evaluateOwnerReadiness,
  hasNoindexRobotsTag,
  productionPageRoutes,
  runNightlyChecks,
  runPostDeploySmoke,
} from "./production-maintenance.mjs";

test("nightly crawl includes live pages but excludes API and dynamic templates", () => {
  assert.deepEqual(
    productionPageRoutes([
      { status: "live", route: "/" },
      { status: "live", route: "/services/$slug" },
      { status: "hidden", route: "/internal" },
      { status: "live", route: "/api/health" },
      { status: "live", route: "/owner" },
    ]),
    ["/", "/owner"],
  );
});

test("owner route must expose a noindex robots tag", () => {
  assert.equal(
    hasNoindexRobotsTag('<meta name="robots" content="noindex, nofollow">'),
    true,
  );
  assert.equal(
    hasNoindexRobotsTag('<meta name="robots" content="index, follow">'),
    false,
  );
});

test("production flag checks fail closed for intake and Forge Bot LIVE", () => {
  assert.deepEqual(evaluateIntakeConfig({ intake_enabled: false }), []);
  assert.match(
    evaluateIntakeConfig({ intake_enabled: true })[0],
    /intake_enabled is true/,
  );
  assert.match(
    evaluateIntakeConfig({})[0],
    /intake_enabled is missing or invalid/,
  );

  assert.deepEqual(
    evaluateOwnerReadiness({
      intake_enabled: false,
      live_enabled: false,
      last_maintenance_age_seconds: 3600,
    }),
    [],
  );
  assert.equal(
    evaluateOwnerReadiness({
      intake_enabled: true,
      live_enabled: true,
      last_maintenance_age_seconds: null,
    }).length,
    3,
  );
  assert.match(
    evaluateOwnerReadiness({
      intake_enabled: false,
      live_enabled: false,
      last_maintenance_age_seconds: 48 * 60 * 60 + 1,
    })[0],
    /heartbeat is stale/,
  );
});

test("post-deploy smoke only GETs health/config and rejects enabled intake", async () => {
  const requests = [];
  const failures = await runPostDeploySmoke(
    async (url, options) => {
      requests.push({ url: String(url), options });
      return {
        ok: true,
        status: 200,
        json: async () => ({
          intake_enabled: String(url).includes("haminp"),
        }),
      };
    },
    ["https://haminp.vercel.app", "https://forge-os-ebon.vercel.app"],
  );

  assert.equal(failures.length, 1);
  assert.match(failures[0], /haminp\.vercel\.app.*intake_enabled is true/);
  assert.equal(requests.length, 4);
  assert.ok(requests.every(({ options }) => options.method === "GET"));
  assert.ok(requests.every(({ options }) => !("body" in options)));
});

test("nightly readiness records heartbeat age without leaking the owner key", async () => {
  const requests = [];
  const apiKey = "test-key-must-not-be-logged";
  const result = await runNightlyChecks(
    async (url, options) => {
      requests.push({ url: String(url), options });
      const body = String(url).endsWith("/config")
        ? { intake_enabled: false }
        : String(url).endsWith("/owner/readiness")
          ? {
              intake_enabled: false,
              live_enabled: false,
              last_maintenance_age_seconds: 3600,
            }
          : undefined;
      return {
        ok: true,
        status: 200,
        json: async () => body,
        text: async () => '<meta name="robots" content="noindex, nofollow">',
      };
    },
    {
      domains: ["https://haminp.vercel.app"],
      apiKey,
      features: [{ status: "live", route: "/owner" }],
    },
  );

  assert.deepEqual(result.failures, []);
  assert.equal(result.heartbeatAgeSeconds, 3600);
  assert.ok(requests.every(({ options }) => options.method === "GET"));
  assert.ok(
    requests
      .filter(({ url }) => url.endsWith("/owner/readiness"))
      .every(({ options }) => options.headers["X-API-Key"] === apiKey),
  );
});
