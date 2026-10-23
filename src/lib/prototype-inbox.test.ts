import assert from "node:assert/strict";
import { describe, it } from "node:test";
import {
  isCommitmentEntry,
  isInquiry,
  parseOrderValue,
  summarizeCommitments,
  syncCommitmentEntryToSubstrate,
  type CommitmentEntry,
} from "./prototype-inbox.ts";

describe("parseOrderValue", () => {
  it("keeps decimal amounts intact", () => {
    assert.equal(parseOrderValue("1500.50"), 1500.5);
  });

  it("strips commas and currency symbols", () => {
    assert.equal(parseOrderValue("₨1,500"), 1500);
    assert.equal(parseOrderValue("Rs. 2,250.75"), 2250.75);
  });

  it("plain integers parse as-is", () => {
    assert.equal(parseOrderValue("500"), 500);
  });

  it("empty or garbage input becomes 0, never NaN", () => {
    assert.equal(parseOrderValue(""), 0);
    assert.equal(parseOrderValue(".."), 0);
    assert.equal(parseOrderValue("free"), 0);
  });

  it("multiple dots: last one wins as the decimal separator", () => {
    assert.equal(parseOrderValue("1.2.3"), 12.3);
  });
});

describe("isInquiry", () => {
  const good = {
    id: "1728000000000-abc12",
    timeIn: 1728000000000,
    customer: "Sita",
    want: "red kurta, size M",
    replyAt: null,
    outcome: "open",
    orderValue: null,
  };

  it("accepts a well-formed inquiry", () => {
    assert.equal(isInquiry(good), true);
  });

  it("accepts replied and recovered shapes", () => {
    assert.equal(
      isInquiry({ ...good, replyAt: 1728000060000, outcome: "recovered", orderValue: 250 }),
      true,
    );
  });

  it("rejects non-objects", () => {
    assert.equal(isInquiry(null), false);
    assert.equal(isInquiry("inquiry"), false);
    assert.equal(isInquiry(42), false);
    assert.equal(isInquiry(undefined), false);
  });

  it("rejects wrong field types", () => {
    assert.equal(isInquiry({ ...good, timeIn: "yesterday" }), false);
    assert.equal(isInquiry({ ...good, replyAt: "fast" }), false);
    assert.equal(isInquiry({ ...good, orderValue: "lots" }), false);
  });

  it("rejects unknown outcomes", () => {
    assert.equal(isInquiry({ ...good, outcome: "maybe" }), false);
  });

  it("rejects missing required fields", () => {
    const { want, ...rest } = good;
    void want;
    assert.equal(isInquiry(rest), false);
  });
});

describe("isCommitmentEntry", () => {
  const good: CommitmentEntry = {
    id: "1728000000000-cmt01",
    sellerRef: "seller-01",
    stage: "inquiry",
    at: 1728000000000,
    amount: null,
    verification: "reported",
    evidenceRef: "",
    sellerConsent: false,
    recovered: null,
    note: "Seller reported 12 inquiries on day 1.",
  };

  it("accepts a well-formed reported entry", () => {
    assert.equal(isCommitmentEntry(good), true);
  });

  it("accepts a verified entry with evidence and consent", () => {
    assert.equal(
      isCommitmentEntry({
        ...good,
        stage: "payment",
        amount: 2500,
        verification: "verified",
        evidenceRef: "owner-note-2026-10-24",
        sellerConsent: true,
      }),
      true,
    );
  });

  it("rejects a verified entry without an evidence reference", () => {
    assert.equal(
      isCommitmentEntry({ ...good, verification: "verified", sellerConsent: true }),
      false,
    );
  });

  it("rejects a verified entry without seller consent", () => {
    assert.equal(
      isCommitmentEntry({ ...good, verification: "verified", evidenceRef: "ref-1" }),
      false,
    );
  });

  it("rejects non-objects and wrong field types", () => {
    assert.equal(isCommitmentEntry(null), false);
    assert.equal(isCommitmentEntry("entry"), false);
    assert.equal(isCommitmentEntry({ ...good, at: "today" }), false);
    assert.equal(isCommitmentEntry({ ...good, amount: "lots" }), false);
    assert.equal(isCommitmentEntry({ ...good, sellerConsent: "yes" }), false);
  });

  it("rejects unknown stages and verification states", () => {
    assert.equal(isCommitmentEntry({ ...good, stage: "shipped" }), false);
    assert.equal(isCommitmentEntry({ ...good, verification: "proven" }), false);
  });

  it("rejects a recovered flag on a non-outcome stage", () => {
    assert.equal(isCommitmentEntry({ ...good, recovered: true }), false);
    assert.equal(
      isCommitmentEntry({ ...good, stage: "outcome", recovered: false }),
      true,
    );
  });
});

describe("summarizeCommitments", () => {
  const base: CommitmentEntry = {
    id: "x",
    sellerRef: "seller-01",
    stage: "inquiry",
    at: 1728000000000,
    amount: null,
    verification: "reported",
    evidenceRef: "",
    sellerConsent: false,
    recovered: null,
    note: "",
  };

  it("empty log summarizes to honest zeros", () => {
    const s = summarizeCommitments([]);
    assert.equal(s.entries, 0);
    assert.equal(s.inquiries, 0);
    assert.equal(s.orders, 0);
    assert.equal(s.recoveredSales, 0);
    assert.equal(s.rupeesReported, 0);
    assert.equal(s.rupeesVerified, 0);
  });

  it("reported money never counts as verified", () => {
    const s = summarizeCommitments([
      { ...base, id: "1", stage: "payment", amount: 3000 },
      {
        ...base,
        id: "2",
        stage: "payment",
        amount: 1500,
        verification: "verified",
        evidenceRef: "ref-2",
        sellerConsent: true,
      },
    ]);
    assert.equal(s.rupeesReported, 3000);
    assert.equal(s.rupeesVerified, 1500);
  });

  it("counts stages and recovered outcomes; unverified outcomes do not count as recovered sales", () => {
    const s = summarizeCommitments([
      { ...base, id: "1", stage: "inquiry" },
      { ...base, id: "2", stage: "inquiry" },
      { ...base, id: "3", stage: "order", amount: 900 },
      { ...base, id: "4", stage: "outcome", recovered: true },
      {
        ...base,
        id: "5",
        stage: "outcome",
        recovered: true,
        verification: "verified",
        evidenceRef: "ref-5",
        sellerConsent: true,
      },
      { ...base, id: "6", stage: "outcome", recovered: false },
    ]);
    assert.equal(s.inquiries, 2);
    assert.equal(s.orders, 1);
    assert.equal(s.recoveredSales, 1);
  });
});


describe("syncCommitmentEntryToSubstrate", () => {
  const entry: CommitmentEntry = {
    id: "entry-01",
    sellerRef: "seller-01",
    stage: "payment",
    at: 1792750000000,
    amount: 1250,
    verification: "reported",
    evidenceRef: "owner-reference-01",
    sellerConsent: true,
    recovered: null,
    note: "PRIVATE FREE TEXT MUST NEVER LEAVE THE BROWSER",
  };

  it("writes idempotent entity/relation/evidence/event records and excludes the note", async () => {
    const calls: Array<{ url: string; method: string; headers: HeadersInit; body?: Record<string, unknown> }> = [];
    const store = {
      sellers: [] as Array<{ id: number; attributes: Record<string, unknown> }>,
      commitments: [] as Array<{ id: number; attributes: Record<string, unknown> }>,
    };
    let nextId = 1;
    const fetcher: typeof fetch = async (input, init) => {
      const url = String(input);
      const method = String(init?.method ?? "GET");
      const headers = init?.headers ?? {};
      const body = typeof init?.body === "string" ? JSON.parse(init.body) as Record<string, unknown> : undefined;
      calls.push({ url, method, headers, body });

      if (method === "GET" && url.includes("entity_type=scout_candidate")) {
        return new Response(JSON.stringify(store.sellers), { status: 200 });
      }
      if (method === "GET" && url.includes("entity_type=commitment")) {
        return new Response(JSON.stringify(store.commitments), { status: 200 });
      }
      if (method === "POST" && url.endsWith("/entities")) {
        const row = { id: nextId++, attributes: body?.attributes as Record<string, unknown> };
        if (body?.entity_type === "scout_candidate") store.sellers.push(row);
        else store.commitments.push(row);
        return new Response(JSON.stringify(row), { status: 201 });
      }
      if (method === "POST" && url.endsWith("/relations")) {
        return new Response(JSON.stringify({ id: nextId++ }), { status: 201 });
      }
      if (method === "POST" && url.endsWith("/evidence")) {
        return new Response(JSON.stringify({ legacy_ref: { id: nextId++ } }), { status: 201 });
      }
      if (method === "POST" && url.endsWith("/events")) {
        return new Response(JSON.stringify({ id: nextId++ }), { status: 201 });
      }
      return new Response(JSON.stringify({ detail: "unexpected request" }), { status: 404 });
    };

    const result = await syncCommitmentEntryToSubstrate(entry, "owner-secret-in-memory", fetcher);
    assert.equal(result.sellerEntityId, 1);
    assert.equal(result.commitmentEntityId, 2);
    assert.equal(result.relationId, 3);
    assert.equal(result.evidenceId, 4);
    assert.equal(result.eventId, 5);
    assert.ok(result.syncedAt);
    assert.ok(calls.every((call) => {
      const headers = new Headers(call.headers);
      return headers.get("X-API-Key") === "owner-secret-in-memory";
    }));
    assert.equal(calls.some((call) => JSON.stringify(call.body ?? {}).includes("PRIVATE FREE TEXT")), false);
    assert.equal(calls.find((call) => call.url.endsWith("/evidence"))?.body?.support_level, "unknown");
    assert.equal(calls.find((call) => call.url.endsWith("/events"))?.body?.payload && JSON.stringify(calls.find((call) => call.url.endsWith("/events"))?.body?.payload).includes("PRIVATE FREE TEXT"), false);
  });

  it("refuses to sync without consent", async () => {
    let calls = 0;
    const fetcher: typeof fetch = async () => {
      calls += 1;
      return new Response("{}", { status: 200 });
    };
    await assert.rejects(
      syncCommitmentEntryToSubstrate({ ...entry, sellerConsent: false }, "owner-key", fetcher),
      /Seller consent is required/,
    );
    assert.equal(calls, 0);
  });

  it("rejects seller identifiers that could contain names or contact data", async () => {
    let calls = 0;
    const fetcher: typeof fetch = async () => {
      calls += 1;
      return new Response("{}", { status: 200 });
    };
    await assert.rejects(
      syncCommitmentEntryToSubstrate({ ...entry, sellerRef: "Niroj Paudyal" }, "owner-key", fetcher),
      /pseudonymous seller reference/,
    );
    assert.equal(calls, 0);
  });

  it("does not claim sync succeeded when the maintenance gate returns 503", async () => {
    const fetcher: typeof fetch = async () => new Response(
      JSON.stringify({ detail: "Hami is under development." }),
      { status: 503 },
    );
    await assert.rejects(
      syncCommitmentEntryToSubstrate(entry, "owner-key", fetcher),
      /maintenance gate may still be active/,
    );
  });
});
