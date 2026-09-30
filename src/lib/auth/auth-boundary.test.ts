import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { describe, it } from "node:test";
import { AUTH_PROVIDERS } from "./providers.ts";

const read = (file: string) =>
  readFileSync(new URL(file, import.meta.url), "utf8");

describe("Hami authentication boundary", () => {
  it("offers direct Google only and never exposes X as a provider", () => {
    assert.deepEqual(AUTH_PROVIDERS, [{ providerId: "google", label: "Google" }]);
    const providers = read("./providers.ts");
    const login = read("../../routes/login.tsx");
    assert.match(providers, /providerId:\s*"google",\s*label:\s*"Google"/);
    assert.match(login, /AUTH_PROVIDERS\.map/);
    assert.match(login, /Continue with \{provider\.label\}/);
    assert.doesNotMatch(login, /Continue with X|Twitter|GROK_PROVIDERS/);
  });

  it("uses only server-side Google credentials and never a broker fallback", () => {
    const server = read("./server.ts");
    assert.match(server, /GOOGLE_CLIENT_ID/);
    assert.match(server, /GOOGLE_CLIENT_SECRET/);
    assert.match(server, /socialProviders:\s*\{\s*google:/);
    assert.match(server, /disableImplicitSignUp:\s*true/);
    assert.doesNotMatch(server, /auth\.grok\.me|GROK_AUTH_CLIENT_SECRET|genericOAuth/);
    assert.doesNotMatch(read("./preview.ts"), /PREVIEW_CLIENT_SECRET|[a-f0-9]{64}/i);
  });

  it("rejects new users server-side without a single-use adult/terms permit", () => {
    const server = read("./server.ts");
    assert.match(server, /databaseHooks:\s*\{[\s\S]*?user:\s*\{[\s\S]*?create:\s*\{/);
    assert.match(server, /consumeSignupPermit/);
    assert.match(server, /throw new APIError\("FORBIDDEN"/);
    assert.match(server, /termsVersion:\s*\{\s*type:\s*"string"[\s\S]*?returned:\s*false/);
    assert.match(server, /termsAcceptedAt:\s*\{\s*type:\s*"date"[\s\S]*?returned:\s*false/);
    assert.doesNotMatch(server, /dateOfBirth:\s*\{/);
  });

  it("keeps DOB and private consent metadata out of public projections", () => {
    const publicFiles = [
      "../../lib/content.ts",
      "../../routes/feed.tsx",
      "../../routes/discoveries.tsx",
      "../../routes/opportunities.tsx",
    ].map(read).join("\n");
    assert.doesNotMatch(publicFiles, /dateOfBirth|termsVersion|termsAcceptedAt|user_personal_context/);
    assert.match(read("./terms-policy.ts"), /ACTIVE_TERMS.*null/);
  });
});
