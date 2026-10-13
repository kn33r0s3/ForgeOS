import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import test from "node:test";

const ROOT = join(dirname(fileURLToPath(import.meta.url)), "..");
const WORKFLOW = join(ROOT, ".github/workflows/verify-deploy.yml");

test("a failed current verification is recorded before the workflow returns failure", () => {
  const source = readFileSync(WORKFLOW, "utf8");
  const record = source.indexOf("- name: Record verification");
  const verdict = source.indexOf("- name: Fail workflow when current verification verdict is false");
  const superseded = source.indexOf("- name: Fail superseded run without recording a verdict");

  assert.ok(record >= 0, "the append-only verification record step must exist");
  assert.ok(verdict > record, "the current-revision verdict gate must run after the record step");
  assert.match(
    source.slice(verdict, superseded),
    /if:\s*steps\.freshness\.outputs\.current\s*==\s*'true'\s*&&\s*steps\.result\.outputs\.passed\s*!=\s*'true'/,
  );
  assert.match(source.slice(verdict, superseded), /exit 1/);
  assert.match(source.slice(record, verdict), /Verification recorded successfully\./);

  // A superseded SHA must fail without polluting the append-only verdict
  // ledger, then still return a failing workflow result.
  assert.ok(superseded > verdict, "superseded-run gate must be explicit");
  assert.match(
    source.slice(superseded),
    /steps\.freshness\.outputs\.current\s*!=\s*'true'/,
  );
  assert.match(source.slice(superseded), /verification was not recorded/i);
  assert.match(source.slice(superseded), /exit 1/);
});
