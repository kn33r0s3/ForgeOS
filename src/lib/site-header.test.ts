import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { describe, it } from "node:test";
import { fileURLToPath } from "node:url";

const __dirname = dirname(fileURLToPath(import.meta.url));
const HEADER_PATH = join(__dirname, "../components/layout/site-header.tsx");

describe("SiteHeader responsive account actions", () => {
  const source = readFileSync(HEADER_PATH, "utf-8");

  it("renders Contact as a regular item in both navigation menus", () => {
    assert.equal((source.match(/NAV\.map\(\(item/g) ?? []).length, 2);
    assert.match(source, /aria-label="Main navigation"[\s\S]*NAV\.map/);
    assert.match(source, /aria-label="Mobile navigation"[\s\S]*NAV\.map/);
    assert.doesNotMatch(source, /to="\/contact"/);
  });

  it("mobile drawer contains Join Hami link", () => {
    // The mobile navigation drawer (id="mobile-navigation") must include
    // the Join Hami action, since the header buttons are hidden below sm:.
    const drawerStart = source.indexOf('id="mobile-navigation"');
    assert.ok(drawerStart !== -1, "Mobile navigation drawer not found");
    const drawerSection = source.slice(drawerStart, drawerStart + 5000);
    assert.ok(
      drawerSection.includes("Join Hami"),
      "Join Hami not found in mobile navigation drawer"
    );
  });

  it("mobile drawer contains Login link", () => {
    const drawerStart = source.indexOf('id="mobile-navigation"');
    assert.ok(drawerStart !== -1, "Mobile navigation drawer not found");
    const drawerSection = source.slice(drawerStart, drawerStart + 5000);
    // Look for the Login link text (not the /login route which appears elsewhere)
    assert.ok(
      drawerSection.includes(">Login<") || drawerSection.includes("Login\n"),
      "Login not found in mobile navigation drawer"
    );
  });

  it("mobile drawer account actions link to /login with correct modes", () => {
    const drawerStart = source.indexOf('id="mobile-navigation"');
    const drawerSection = source.slice(drawerStart, drawerStart + 5000);
    // Join Hami should use sign-up mode
    assert.ok(
      drawerSection.includes('mode: "sign-up"'),
      "Join Hami sign-up mode not found in mobile drawer"
    );
    // Login should use sign-in mode
    assert.ok(
      drawerSection.includes('mode: "sign-in"'),
      "Login sign-in mode not found in mobile drawer"
    );
  });

  it("mobile drawer account actions are not hidden on small screens", () => {
    const drawerStart = source.indexOf('id="mobile-navigation"');
    const drawerSection = source.slice(drawerStart, drawerStart + 5000);
    // The account actions container should NOT have 'hidden' class
    // (they should be visible when the drawer is open)
    const accountSection = drawerSection.indexOf("Account actions:");
    if (accountSection !== -1) {
      const accountDiv = drawerSection.slice(accountSection, accountSection + 500);
      assert.ok(
        !accountDiv.includes('className="hidden'),
        "Mobile account actions should not be hidden"
      );
    }
  });
});
