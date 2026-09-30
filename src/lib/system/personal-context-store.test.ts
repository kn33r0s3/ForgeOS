import assert from "node:assert/strict";
import { PGlite } from "@electric-sql/pglite";
import { readFileSync } from "node:fs";
import { describe, it } from "node:test";
import {
  deleteUserPersonalContext,
  loadUserPersonalContext,
  normalizePersonalContext,
  saveUserPersonalContext,
} from "./personal-context-store.ts";

async function withDb<T>(run: (db: PGlite) => Promise<T>): Promise<T> {
  const db = new PGlite();
  await db.exec(`
    create table "user" (id text primary key);
    create table user_personal_context (
      user_id text primary key references "user" ("id") on delete cascade,
      context jsonb not null check (jsonb_typeof(context) = 'object'),
      created_at timestamptz not null default now(),
      updated_at timestamptz not null default now()
    );
    insert into "user" (id) values ('user-a'), ('user-b');
  `);
  try {
    return await run(db);
  } finally {
    await db.close();
  }
}

function sqlFor(db: PGlite) {
  return {
    async query<T extends Record<string, unknown>>(text: string, params: unknown[] = []) {
      const result = await db.query<T>(text, params);
      return result.rows;
    },
  };
}

function context(location: string) {
  return {
    version: 1,
    location: { value: location, provenance: "stated", updatedAt: "2026-01-01T00:00:00.000Z" },
    capabilities: [],
    resources: [],
    goals: [],
    constraints: [],
    createdAt: "2026-01-01T00:00:00.000Z",
    updatedAt: "2026-01-01T00:00:00.000Z",
  };
}

describe("private personal context storage", () => {
  it("protects every private server function and derives ownership from verified middleware context", () => {
    const source = readFileSync(new URL("./personal-context.ts", import.meta.url), "utf8");
    assert.equal(source.match(/\.middleware\(\[authMiddleware\]\)/g)?.length, 3);
    assert.equal(source.match(/context\.userId/g)?.length, 3);
    assert.doesNotMatch(source, /userId\s*:\s*data/);
  });

  it("clears a guest draft only after an explicitly reviewed account save succeeds", () => {
    const source = readFileSync(new URL("./use-system.ts", import.meta.url), "utf8");
    const saveIndex = source.indexOf("await savePersonalContext({ data: next })");
    const reviewIndex = source.indexOf("if (reviewingTemporary)", saveIndex);
    const clearIndex = source.indexOf("clearGuestState", reviewIndex);

    assert.ok(saveIndex >= 0);
    assert.ok(reviewIndex > saveIndex);
    assert.ok(clearIndex > reviewIndex);
    assert.match(source, /if \(mode === "account" && guestState\)[\s\S]*setReviewingTemporary\(true\)/);
  });

  it("does not add private personal context to public projection clients", () => {
    const publicContent = readFileSync(new URL("../content.ts", import.meta.url), "utf8");
    const publicRoutes = ["feed.tsx", "discoveries.tsx", "opportunities.tsx"]
      .map((route) => readFileSync(new URL(`../../routes/${route}`, import.meta.url), "utf8"))
      .join("\n");

    assert.doesNotMatch(publicContent, /user_personal_context|personal-context/);
    assert.doesNotMatch(publicRoutes, /personal-context|user_personal_context/);
  });

  it("accepts incomplete context and keeps self-reports epistemically stated", () => {
    const normalized = normalizePersonalContext({
      ...context(""),
      location: { value: "Pokhara", provenance: "verified", updatedAt: "earlier" },
      time: undefined,
      resources: [{ value: "  sewing machine ", provenance: "inferred", updatedAt: "earlier" }],
    });
    assert.equal(normalized.location?.value, "Pokhara");
    assert.equal(normalized.location?.provenance, "stated");
    assert.equal(normalized.resources[0]?.value, "sewing machine");
    assert.equal(normalized.resources[0]?.provenance, "stated");
    assert.equal(normalized.time, undefined);
    assert.deepEqual(normalized.goals, []);
  });

  it("scopes reads, writes, and deletion to the verified owner id", async () => {
    await withDb(async (db) => {
      const sql = sqlFor(db);
      await saveUserPersonalContext(sql, "user-a", context("A-only"));
      await saveUserPersonalContext(sql, "user-b", context("B-only"));

      await saveUserPersonalContext(sql, "user-a", {
        ...context("A-updated"),
        userId: "user-b",
      });

      assert.equal((await loadUserPersonalContext(sql, "user-a"))?.location?.value, "A-updated");
      assert.equal((await loadUserPersonalContext(sql, "user-b"))?.location?.value, "B-only");

      await deleteUserPersonalContext(sql, "user-a");
      assert.equal(await loadUserPersonalContext(sql, "user-a"), null);
      assert.equal((await loadUserPersonalContext(sql, "user-b"))?.location?.value, "B-only");
    });
  });

  it("rejects an unsupported context version instead of storing a fallback", async () => {
    await withDb(async (db) => {
      await assert.rejects(
        saveUserPersonalContext(sqlFor(db), "user-a", { ...context("x"), version: 2 }),
        /supported context format/,
      );
      const rows = await db.query<{ count: number }>(
        "select count(*)::int as count from user_personal_context",
      );
      assert.equal(rows.rows[0]?.count, 0);
    });
  });
});
