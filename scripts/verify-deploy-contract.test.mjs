import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import test from "node:test";

const ROOT = join(dirname(fileURLToPath(import.meta.url)), "..");
const WORKFLOW = join(ROOT, ".github/workflows/verify-deploy.yml");

test("a failed verification is recorded before the workflow returns failure", () => {
  const source = readFileSync(WORKFLOW, "utf8");
  const record = source.indexOf("- name: Record verification");
  const verdict = source.indexOf("- name: Fail workflow when verification verdict is false");

  assert.ok(record >= 0, "the append-only verification record step must exist");
  assert.ok(verdict > record, "the verdict gate must run after the record step");
  assert.match(source.slice(verdict), /if:\s*steps\.result\.outputs\.passed\s*!=\s*'true'/);
  assert.match(source.slice(verdict), /exit 1/);
  assert.match(source.slice(record, verdict), /Verification recorded successfully\./);
});
