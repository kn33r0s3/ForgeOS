import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { join } from "node:path";
import { test } from "node:test";
import { projectRoot } from "./with-app-env.mjs";

test("Better Auth API routes reach the web service before the backend API catch-all", () => {
  const config = JSON.parse(readFileSync(join(projectRoot(), "vercel.json"), "utf8"));
  const rewrites = config.rewrites;
  const authIndex = rewrites.findIndex((rule) => rule.source === "/api/auth/(.*)");
  const backendIndex = rewrites.findIndex((rule) => rule.source === "/api/(.*)");

  assert.notEqual(authIndex, -1);
  assert.notEqual(backendIndex, -1);
  assert.ok(authIndex < backendIndex);
  assert.deepEqual(rewrites[authIndex].destination, { service: "web" });
});
