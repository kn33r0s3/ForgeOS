// Pure helpers for the /prototype/inbox sprint-week prototype.
// Kept side-effect free so they can be unit tested; the route owns localStorage.

export type Outcome = "open" | "recovered" | "lost" | "browsing";

export interface Inquiry {
  id: string;
  timeIn: number;
  customer: string;
  want: string;
  replyAt: number | null;
  outcome: Outcome;
  orderValue: number | null;
}

/**
 * Parse a free-typed rupee amount from window.prompt.
 * Keeps digits and a decimal point; commas/currency symbols are stripped.
 * If several dots survive (e.g. the "Rs." prefix), the LAST one is the decimal
 * separator and earlier ones are punctuation noise — this avoids the old
 * inline version's bug of stripping the decimal point too ("1500.50"→150050).
 * Anything still unparseable becomes 0.
 */
export function parseOrderValue(raw: string): number {
  const cleaned = raw.replace(/[^0-9.]/g, "");
  const parts = cleaned.split(".");
  const normalized =
    parts.length <= 2 ? cleaned : parts.slice(0, -1).join("") + "." + parts[parts.length - 1];
  const n = Number(normalized);
  return Number.isFinite(n) ? n : 0;
}

/**
 * Shape guard for inquiry records read back from localStorage. Stored data
 * from an older build — or hand-edited storage — must not crash the page with
 * "Invalid Date" / "NaNh NaNm" rows.
 */
export function isInquiry(x: unknown): x is Inquiry {
  if (typeof x !== "object" || x === null) return false;
  const o = x as Record<string, unknown>;
  return (
    typeof o.id === "string" &&
    typeof o.timeIn === "number" &&
    Number.isFinite(o.timeIn) &&
    typeof o.customer === "string" &&
    typeof o.want === "string" &&
    (o.replyAt === null ||
      (typeof o.replyAt === "number" && Number.isFinite(o.replyAt))) &&
    (o.outcome === "open" ||
      o.outcome === "recovered" ||
      o.outcome === "lost" ||
      o.outcome === "browsing") &&
    (o.orderValue === null ||
      (typeof o.orderValue === "number" && Number.isFinite(o.orderValue)))
  );
}

// ---------------------------------------------------------------------------
// Verified-commitment log (First Rupee Sprint, mission item 4).
//
// One entry per stage of a single commitment: inquiry → order → payment →
// delivery → outcome. This is the six-primitive shape in miniature: the
// seller is an ENTITY (pseudonymous ref only — never a name, phone, or
// handle a customer could be identified by), each entry is an EVENT, and
// `evidenceRef` points at the EVIDENCE held outside this browser (an owner
// note, a screenshot kept by the owner, a REVENUE_LOG row). Money starts
// as REPORTED and may only be marked VERIFIED when an evidence reference
// exists AND the seller consented to the record — the same rule
// docs/REVENUE_LOG.md applies. The guard below enforces that invariant on
// every read, so hand-edited storage cannot smuggle in a "verified" rupee.
// ---------------------------------------------------------------------------

export type CommitmentStage = "inquiry" | "order" | "payment" | "delivery" | "outcome";

export type Verification = "reported" | "verified";

export interface CanonicalCommitmentSync {
  sellerEntityId: number;
  commitmentEntityId: number;
  relationId: number;
  evidenceId: number;
  eventId: number;
  syncedAt: string;
}

export interface CommitmentEntry {
  id: string;
  /** References returned by the existing owner-key-protected Hami substrate APIs. */
  substrateSync?: CanonicalCommitmentSync;
  /** Pseudonymous seller reference (e.g. "seller-01"). Never contact data. */
  sellerRef: string;
  stage: CommitmentStage;
  at: number;
  /** Rupee amount for this stage, when the stage carries one. */
  amount: number | null;
  verification: Verification;
  /** Non-secret pointer to evidence held by the owner. Required for VERIFIED. */
  evidenceRef: string;
  /** True only when the seller consented to this record being kept. */
  sellerConsent: boolean;
  /** Only meaningful on the outcome stage: did this sale recover? */
  recovered: boolean | null;
  note: string;
}

const COMMITMENT_STAGES: readonly string[] = ["inquiry", "order", "payment", "delivery", "outcome"];

/**
 * Shape + invariant guard for commitment entries read back from storage.
 * VERIFIED requires an evidence reference and seller consent; a recovered
 * flag is only valid on the outcome stage.
 */
export function isCommitmentEntry(x: unknown): x is CommitmentEntry {
  if (typeof x !== "object" || x === null) return false;
  const o = x as Record<string, unknown>;
  if (
    typeof o.id !== "string" ||
    typeof o.sellerRef !== "string" ||
    typeof o.stage !== "string" ||
    !COMMITMENT_STAGES.includes(o.stage) ||
    typeof o.at !== "number" ||
    !Number.isFinite(o.at) ||
    !(o.amount === null || (typeof o.amount === "number" && Number.isFinite(o.amount))) ||
    !(o.verification === "reported" || o.verification === "verified") ||
    typeof o.evidenceRef !== "string" ||
    typeof o.sellerConsent !== "boolean" ||
    !(o.recovered === null || typeof o.recovered === "boolean") ||
    typeof o.note !== "string"
  ) {
    return false;
  }
  if (o.verification === "verified" && (o.evidenceRef.trim() === "" || o.sellerConsent !== true)) {
    return false;
  }
  if (o.substrateSync !== undefined) {
    const sync = o.substrateSync as Record<string, unknown>;
    if (
      typeof sync !== "object" || sync === null ||
      !["sellerEntityId", "commitmentEntityId", "relationId", "evidenceId", "eventId"]
        .every((key) => Number.isInteger(sync[key]) && Number(sync[key]) > 0) ||
      typeof sync.syncedAt !== "string" || sync.syncedAt.trim() === ""
    ) return false;
  }
  if (o.recovered !== null && o.stage !== "outcome") {
    return false;
  }
  return true;
}

export interface CommitmentSummary {
  entries: number;
  inquiries: number;
  orders: number;
  payments: number;
  deliveries: number;
  outcomes: number;
  /** Outcome entries marked recovered AND verified — the only count the
   *  scoreboard may call recovered sales. */
  recoveredSales: number;
  /** Sum of payment-stage amounts still at REPORTED. */
  rupeesReported: number;
  /** Sum of payment-stage amounts at VERIFIED (evidence + consent). */
  rupeesVerified: number;
}

/**
 * Aggregate a commitment log for the scoreboard. Reported money and
 * verified money are summed separately and never merged; an outcome only
 * counts as a recovered sale when it is verified.
 */
export function summarizeCommitments(entries: CommitmentEntry[]): CommitmentSummary {
  const s: CommitmentSummary = {
    entries: entries.length,
    inquiries: 0,
    orders: 0,
    payments: 0,
    deliveries: 0,
    outcomes: 0,
    recoveredSales: 0,
    rupeesReported: 0,
    rupeesVerified: 0,
  };
  for (const e of entries) {
    if (e.stage === "inquiry") s.inquiries += 1;
    if (e.stage === "order") s.orders += 1;
    if (e.stage === "delivery") s.deliveries += 1;
    if (e.stage === "payment") {
      s.payments += 1;
      if (e.amount !== null) {
        if (e.verification === "verified") s.rupeesVerified += e.amount;
        else s.rupeesReported += e.amount;
      }
    }
    if (e.stage === "outcome") {
      s.outcomes += 1;
      if (e.recovered === true && e.verification === "verified") s.recoveredSales += 1;
    }
  }
  return s;
}


export type SubstrateSyncResult = CanonicalCommitmentSync;

interface SubstrateEntity {
  id: number;
  attributes?: Record<string, unknown>;
}
interface SubstrateRelation { id: number }
interface SubstrateEvidence { legacy_ref?: { id?: number } }
interface SubstrateEvent { id: number }

/**
 * Persist an owner-entered commitment-log stage through Hami's existing
 * owner-key-protected six-primitive substrate APIs. This never sends the
 * free-text note, a customer name, a phone number, or a social handle.
 * The evidence record describes the source log entry and explicitly records
 * that the referenced proof was not inspected by this connector.
 */
export async function syncCommitmentEntryToSubstrate(
  entry: CommitmentEntry,
  ownerKey: string,
  fetcher: typeof fetch = fetch,
): Promise<SubstrateSyncResult> {
  if (!isCommitmentEntry(entry)) {
    throw new Error("Commitment entry is malformed; nothing was synced.");
  }
  if (!/^seller-[a-z0-9][a-z0-9_-]{0,31}$/i.test(entry.sellerRef)) {
    throw new Error("Use a pseudonymous seller reference like seller-01; names and contact details are not allowed.");
  }
  if (entry.sellerConsent !== true) {
    throw new Error("Seller consent is required before syncing this record.");
  }
  if (!ownerKey.trim()) {
    throw new Error("Enter the owner API key to sync; it is used in memory only.");
  }
  const headers = { "X-API-Key": ownerKey, "Content-Type": "application/json" };

  async function request<T>(path: string, method = "GET", body?: unknown): Promise<T> {
    let response: Response;
    try {
      response = await fetcher(path, {
        method,
        headers,
        ...(body === undefined ? {} : { body: JSON.stringify(body) }),
      });
    } catch {
      throw new Error("Hami substrate could not be reached. The entry remains only in this browser.");
    }
    if (!response.ok) {
      // Deliberately avoid echoing the body; do not surface arbitrary server text.
      throw new Error(
        response.status === 503
          ? "Hami substrate is unavailable (HTTP 503). The production maintenance gate may still be active; do not bypass it."
          : `Hami substrate rejected the request (HTTP ${response.status}); the entry remains in this browser.`,
      );
    }
    try {
      return await response.json() as T;
    } catch {
      throw new Error("Hami substrate returned an unreadable response; sync is not confirmed.");
    }
  }

  async function ensureEntity(
    type: "scout_candidate" | "commitment",
    displayName: string,
    marker: string,
    markerValue: string,
    attributes: Record<string, unknown>,
  ): Promise<number> {
    const rows = await request<SubstrateEntity[]>(
      `/api/forge/substrate/entities?entity_type=${type}&limit=500`,
    );
    if (!Array.isArray(rows)) throw new Error("Hami substrate entity list was not an array.");
    const existing = rows.find((row) => row.attributes?.[marker] === markerValue);
    if (existing && Number.isInteger(existing.id) && existing.id > 0) return existing.id;

    const created = await request<SubstrateEntity>("/api/forge/substrate/entities", "POST", {
      entity_type: type,
      display_name: displayName,
      attributes,
      created_by: "first_rupee_commitment_log",
    });
    if (!Number.isInteger(created.id) || created.id <= 0) {
      throw new Error("Hami substrate did not return an entity ID; sync is not confirmed.");
    }
    return created.id;
  }

  const sellerEntityId = await ensureEntity(
    "scout_candidate",
    entry.sellerRef,
    "first_rupee_seller_ref",
    entry.sellerRef,
    { source_app: "first_rupee_commitment_log", first_rupee_seller_ref: entry.sellerRef },
  );
  const commitmentEntityId = await ensureEntity(
    "commitment",
    `commitment:${entry.id}`,
    "first_rupee_entry_id",
    entry.id,
    {
      source_app: "first_rupee_commitment_log",
      first_rupee_entry_id: entry.id,
      seller_ref: entry.sellerRef,
      stage: entry.stage,
      amount_npr: entry.amount,
      log_verification_label: entry.verification,
      seller_consent: true,
      evidence_reference: entry.evidenceRef,
      recovered: entry.recovered,
      record_semantics: "owner-entered log; verification label is not independently validated by this connector",
    },
  );

  const relation = await request<SubstrateRelation>("/api/forge/substrate/relations", "POST", {
    from_entity_id: sellerEntityId,
    to_entity_id: commitmentEntityId,
    relation_type: "tracks",
    attributes: { source_app: "first_rupee_commitment_log", first_rupee_entry_id: entry.id },
    direction: "directed",
    strength: 1,
    truth_state: "hypothesized",
    created_by: "first_rupee_commitment_log",
    idempotency_key: `first-rupee:relation:${entry.id}`,
  });
  if (!Number.isInteger(relation.id) || relation.id <= 0) {
    throw new Error("Hami substrate did not return a relation ID; sync is not confirmed.");
  }

  const evidence = await request<SubstrateEvidence>("/api/forge/substrate/evidence", "POST", {
    subject_kind: "relation",
    subject_id: relation.id,
    claim: `Owner-entered commitment log records stage '${entry.stage}' for pseudonymous seller '${entry.sellerRef}'. Source form label: '${entry.verification}'. The connector did not inspect the referenced evidence; this record does not independently verify a payment, delivery, or recovered sale.`,
    support_level: "unknown",
    source: "first_rupee_commitment_log",
    provenance: {
      source_app: "first_rupee_commitment_log",
      entry_id: entry.id,
      seller_ref: entry.sellerRef,
      stage: entry.stage,
      amount_npr: entry.amount,
      log_verification_label: entry.verification,
      seller_consent: true,
      evidence_reference: entry.evidenceRef,
      recovered: entry.recovered,
      note_excluded: true,
      underlying_proof_inspected_by_connector: false,
    },
    idempotency_key: `first-rupee:evidence:${entry.id}`,
  });
  const evidenceId = evidence.legacy_ref?.id;
  if (!Number.isInteger(evidenceId) || (evidenceId as number) <= 0) {
    throw new Error("Hami substrate did not return an evidence reference; sync is not confirmed.");
  }

  const event = await request<SubstrateEvent>("/api/forge/substrate/events", "POST", {
    event_type: "state_changed",
    source: "first_rupee_commitment_log",
    entity_id: commitmentEntityId,
    occurred_at: new Date(entry.at).toISOString(),
    payload: {
      domain: "first_rupee_commitment",
      entry_id: entry.id,
      seller_ref: entry.sellerRef,
      stage: entry.stage,
      relation_id: relation.id,
      evidence_id: evidenceId,
      log_verification_label: entry.verification,
      seller_consent: true,
      amount_npr: entry.amount,
      recovered: entry.recovered,
      note_excluded: true,
      underlying_proof_inspected_by_connector: false,
    },
    idempotency_key: `first-rupee:event:${entry.id}`,
  });
  if (!Number.isInteger(event.id) || event.id <= 0) {
    throw new Error("Hami substrate did not return an event ID; sync is not confirmed.");
  }

  return {
    sellerEntityId,
    commitmentEntityId,
    relationId: relation.id,
    evidenceId: evidenceId as number,
    eventId: event.id,
    syncedAt: new Date().toISOString(),
  };
}
