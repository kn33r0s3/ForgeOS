import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { PGlite } from "@electric-sql/pglite";
import { describe, it } from "node:test";

const migrations = [
  "../../../migrations/0001_auth.sql",
  "../../../migrations/0002_user_personal_context.sql",
  "../../../migrations/0003_auth_terms_consent.sql",
].map((path) => readFileSync(new URL(path, import.meta.url), "utf8"));

describe("private signup consent schema", () => {
  it("applies repeatedly, records only terms consent, and never adds a DOB field", async () => {
    const db = new PGlite();
    try {
      for (const migration of migrations) await db.exec(migration);
      for (const migration of migrations) await db.exec(migration);

      await db.query(
        `insert into "user"
          ("id", "name", "email", "emailVerified", "termsVersion", "termsAcceptedAt")
         values ($1, $2, $3, $4, $5, $6)`,
        ["test-user", "TEST User", "test@example.invalid", false, "TEST-terms-v1", new Date()],
      );
      const user = await db.query<{
        termsVersion: string;
        termsAcceptedAt: Date;
      }>(
        `select "termsVersion", "termsAcceptedAt" from "user" where "id" = $1`,
        ["test-user"],
      );
      assert.equal(user.rows[0]?.termsVersion, "TEST-terms-v1");
      assert.ok(user.rows[0]?.termsAcceptedAt);

      const dobColumn = await db.query(
        `select column_name from information_schema.columns
         where table_name = 'user' and column_name ilike '%birth%'`,
      );
      assert.deepEqual(dobColumn.rows, []);
    } finally {
      await db.close();
    }
  });
});
