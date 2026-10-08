import assert from "node:assert/strict";
import test from "node:test";
import {
  compareTestIntegrity,
  findForbiddenNewFiles,
  findHomeNavigationViolations,
  hasRequiredPrDescription,
  homeNavigationSources,
} from "./maintenance-guards.mjs";

test("blocks newly added versioned and parallel-implementation filenames", () => {
  assert.deepEqual(
    findForbiddenNewFiles([
      "src/engine_v2.ts",
      "backend/app/new_selector.py",
      "docs/selection_new.md",
      "src/engine.ts",
    ]),
    ["src/engine_v2.ts", "backend/app/new_selector.py", "docs/selection_new.md"],
  );
});

test("only checks the home hero, menu, and footer for experiment surfaces", () => {
  assert.deepEqual(
    findHomeNavigationViolations({
      hero: '<Link to="/experiments">The real log</Link>',
      menu: 'NAV = [{ label: "Home", to: "/" }]',
      footer: "Public observations and legal information",
    }),
    ["Home hero links to or promotes an experiment, prototype, or inbox."],
  );
  assert.deepEqual(
    findHomeNavigationViolations({
      hero: "Discover what matters.",
      menu: 'NAV = [{ label: "Inbox", to: "/prototype/inbox" }]',
      footer: 'CURRENT_LINKS = [{ label: "Action state", to: "/actions" }]',
    }),
    ["Top menu links to or promotes an experiment, prototype, or inbox."],
  );
  assert.deepEqual(
    findHomeNavigationViolations({
      hero: "Discover what matters.",
      menu: 'NAV = [{ label: "Home", to: "/" }]',
      footer: 'CURRENT_LINKS = [{ label: "Experiment 1", to: "/needs" }]',
    }),
    ["Footer links to or promotes an experiment, prototype, or inbox."],
  );
});

test("the current home hero, top menu, and footer contain no restricted links", () => {
  assert.deepEqual(
    findHomeNavigationViolations(homeNavigationSources()),
    [],
  );
});

test("requires the PR test baseline and blocks deleted tests or reduced assertions", () => {
  const base = {
    "backend/tests/test_contract.py": "assert first\nassert second\n",
    "src/lib/sample.test.ts": "assert.equal(1, 1);\nassert.ok(true);\n",
  };
  const deleted = compareTestIntegrity(
    base,
    {},
    { tier2Approved: false },
  );
  assert.equal(deleted.ok, false);
  assert.deepEqual(deleted.deletedFiles, [
    "backend/tests/test_contract.py",
    "src/lib/sample.test.ts",
  ]);

  const reduced = compareTestIntegrity(
    base,
    {
      "backend/tests/test_contract.py": "assert first\n",
      "src/lib/sample.test.ts": "assert.equal(1, 1);\n",
    },
    { tier2Approved: false },
  );
  assert.equal(reduced.ok, false);
  assert.equal(reduced.baseAssertions, 4);
  assert.equal(reduced.headAssertions, 2);
});

test("tier-2-approved is the explicit exception for test reductions", () => {
  const result = compareTestIntegrity(
    { "tests/sample.test.mjs": "assert.equal(1, 1);\n" },
    {},
    { tier2Approved: true },
  );
  assert.equal(result.ok, true);
});

test("PR description requires the plain-English context heading", () => {
  assert.equal(
    hasRequiredPrDescription(
      "## What changed, which existing code, what is still unknown\n\nDetails.",
    ),
    true,
  );
  assert.equal(hasRequiredPrDescription("## What changed\n\nDetails."), false);
});
