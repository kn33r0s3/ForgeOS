/**
 * Public, deterministic evidence triage. This module deliberately has no
 * filesystem, network, database, command, or model dependency.
 */
export const SERVICE_VERSION = "0.1.0";
export const MAX_INPUT_BYTES = 12 * 1024;
export const MAX_TEXT_CHARS = 11_500;
export const EXECUTION_BUDGET_MS = 25;

export type SourceKind = "user_report" | "public_post" | "review" | "forum" | "document" | "other";

export type TriageInput = {
  text: string;
  source_kind: SourceKind;
  source_reliability: number;
};

export type EconomicExtraction = {
  problem: string | null;
  affected_customer: string | null;
  customer_type: string | null;
  pain: string | null;
  consequence: string | null;
  existing_solution: string | null;
  desired_outcome: string | null;
  buying_intent: boolean;
  urgency: boolean;
  frequency: string | null;
  monetary_impact: string | null;
  evidence_text: string;
};

const painPhrases = ["complain", "complaint", "frustrat", "annoyed", "fed up", "sick of", "waste time", "wasting time", "waste of time", "costing", "losing customers", "losing money", "lose money", "can't keep up", "cant keep up", "overwhelmed", "struggling", "struggle", "hate having to", "dread", "nightmare", "spend hours", "spending hours", "hours every", "hours a week", "hours per week", "manually"];
const consequencePhrases = ["costing", "losing", "lost", "missed out", "miss out", "cost us", "cost me", "lost revenue", "lost business", "lost customers", "lost sales"];
const desirePhrases = ["wish there was", "wish i had", "need a way to", "looking for a way", "would pay for", "would love a tool", "if only there was", "someone should build"];
const buyingIntentPhrases = ["would pay", "willing to pay", "looking to buy", "shopping for", "any recommendations for a tool", "what do you use for", "paying for"];
const urgencyPhrases = ["asap", "urgent", "immediately", "right now", "every week", "every day", "constantly", "every single time", "again and again", "repeatedly"];
const existingSolutionPhrases = ["currently using", "we use", "tried using", "switched from", "instead of", "manually", "by hand", "spreadsheet", "spreadsheets"];
const customerTypes = ["dentist", "dentists", "contractor", "contractors", "restaurant", "restaurants", "shop owner", "shop owners", "small business", "small businesses", "freelancer", "freelancers", "landlord", "landlords", "clinic", "clinics", "salon", "salons", "plumber", "plumbers", "electrician", "electricians", "agency", "agencies", "consultant", "consultants", "retailer", "retailers", "startup", "startups", "repair shop", "repair shops", "property manager", "property managers", "accounting practice", "accounting practices", "accountant", "accountants", "law firm", "law firms", "lawyer", "lawyers", "bookkeeper", "bookkeepers", "practice", "practices", "gym", "gyms", "fitness studio", "fitness studios", "childcare", "daycare", "veterinarian", "veterinarians", "vet clinic", "vet clinics", "warehouse", "warehouses", "manufacturer", "manufacturers", "factory", "factories", "logistics", "courier", "couriers", "delivery driver", "delivery drivers", "coach", "coaches", "instructor", "instructors", "tutor", "tutors"];
const importance = {
  pain: ["lose", "losing", "lost", "problem", "problems", "struggle", "struggling", "expensive", "difficult", "waste", "wasting", "cannot", "can't", "slow", "frustrating"],
  business: ["customer", "customers", "money", "revenue", "company", "companies", "business", "businesses", "client", "clients", "sales"],
  urgency: ["need", "needs", "immediately", "critical", "urgent", "asap"],
};

function findAny(text: string, phrases: readonly string[]) {
  const lower = text.toLowerCase();
  return phrases
    .filter((phrase) => lower.includes(phrase))
    .sort((a, b) => b.length - a.length)
    [0] ?? null;
}

function round1(value: number) { return Math.round(value * 10) / 10; }

export function validateInput(value: unknown): TriageInput {
  if (!value || typeof value !== "object" || Array.isArray(value)) throw new TriageError("INVALID_INPUT", "Expected a JSON object.");
  const input = value as Record<string, unknown>;
  const allowed = new Set(["text", "source_kind", "source_reliability"]);
  if (Object.keys(input).some((key) => !allowed.has(key))) throw new TriageError("INVALID_INPUT", "Unexpected input field.");
  if (typeof input.text !== "string" || !input.text.trim() || input.text.length > MAX_TEXT_CHARS) throw new TriageError("INVALID_INPUT", "text must be a non-empty string within the limit.");
  if (!(["user_report", "public_post", "review", "forum", "document", "other"] as string[]).includes(input.source_kind as string)) throw new TriageError("INVALID_INPUT", "source_kind is invalid.");
  if (typeof input.source_reliability !== "number" || !Number.isFinite(input.source_reliability) || input.source_reliability < 0 || input.source_reliability > 100) throw new TriageError("INVALID_INPUT", "source_reliability must be a finite number from 0 to 100.");
  return { text: input.text.trim(), source_kind: input.source_kind as SourceKind, source_reliability: input.source_reliability };
}

export class TriageError extends Error {
  public readonly code: string;

  constructor(code: string, message: string) {
    super(message);
    this.code = code;
  }
}

export function extractEconomicEvidence(text: string): EconomicExtraction {
  const affected =
    /\b(one|two|three|four|five|six|seven|eight|nine|ten|\d+)\b\s+(owners|operators|businesses|startups|shops|managers|practices|clinics|studios|firms|agencies|restaurants|contractors|freelancers|vendors|retailers|salons|gyms|schools|teachers|students|dentists|veterinarians|customers|clients)\b/i.exec(text)?.[0] ?? null;
  const frequency = /\b(\d+)\+?\s*(hours?|hrs?|times?|days?|weeks?|customers?|clients?|people)\b/i.exec(text)?.[0] ?? null;
  const money = /\$\s?\d[\d,]*(\.\d+)?|\b\d+\s?(dollars|usd)\b/i.exec(text)?.[0] ?? null;
  const customerType = customerTypes.find((term) => text.toLowerCase().includes(term)) ?? /\b(?:(small|independent|local|indie|solo|tiny|boutique|online|digital|many)\s+)?(?:(\d+)\s+)?(owners|operators|businesses|startups|shops|managers|practices|clinics|studios|firms|agencies|restaurants|contractors|freelancers|vendors|retailers|salons|gyms|schools|teachers|students|dentists|veterinarians)\b/i.exec(text)?.[0] ?? null;
  const pain =
    /\bwasting\s+\d+\s+(?:hours?|hrs?)\b/i.test(text)
      ? "wasting time"
      : findAny(text, painPhrases);
  const consequence = findAny(text, consequencePhrases);
  return { problem: pain || consequence ? text.trim() : null, affected_customer: affected, customer_type: customerType, pain, consequence, existing_solution: findAny(text, existingSolutionPhrases), desired_outcome: findAny(text, desirePhrases), buying_intent: findAny(text, buyingIntentPhrases) !== null, urgency: findAny(text, urgencyPhrases) !== null, frequency, monetary_impact: money, evidence_text: text.trim() };
}

export function scoreEvidence(extraction: EconomicExtraction, reliability: number) {
  const economic = {
    pain_score: extraction.pain ? 70 : 0,
    urgency_score: extraction.urgency ? 60 : 0,
    monetary_impact_score: extraction.monetary_impact || extraction.consequence ? 80 : 0,
    demand_score: extraction.buying_intent ? 90 : extraction.desired_outcome ? 50 : 0,
    solution_gap_score: extraction.existing_solution ? 60 : 0,
    evidence_strength: (extraction.problem ? 50 : 0) + (extraction.customer_type || extraction.affected_customer ? 50 : 0),
    source_quality: reliability,
  };
  const normalized = extraction.evidence_text.toLowerCase().replace(/\s+/g, " ");
  const count = (words: string[]) => words.filter((word) => normalized.includes(word)).length;
  const rank = { pain_matches: count(importance.pain), business_matches: count(importance.business), urgency_matches: count(importance.urgency) };
  const importanceScore = Math.min(100, 25 + Math.min(40, rank.pain_matches * 18) + Math.min(30, rank.business_matches * 12) + Math.min(30, rank.urgency_matches * 20));
  return { economic, importance: { score: round1(importanceScore), ...rank, pain_score: Math.min(40, rank.pain_matches * 18), business_score: Math.min(30, rank.business_matches * 12), urgency_score: Math.min(30, rank.urgency_matches * 20), base_score: 25 } };
}

function canonical(value: unknown): string {
  if (Array.isArray(value)) return `[${value.map(canonical).join(",")}]`;
  if (value && typeof value === "object") return `{${Object.entries(value as Record<string, unknown>).sort(([a], [b]) => a.localeCompare(b)).map(([k, v]) => `${JSON.stringify(k)}:${canonical(v)}`).join(",")}}`;
  return JSON.stringify(value);
}

async function sha256(value: string): Promise<string> {
  const bytes = new TextEncoder().encode(value);
  const digest = await crypto.subtle.digest("SHA-256", bytes);
  return Array.from(new Uint8Array(digest), (byte) => byte.toString(16).padStart(2, "0")).join("");
}

export async function triage(inputValue: unknown) {
  const input = validateInput(inputValue);
  const input_hash = await sha256(canonical(input));
  const evidence = extractEconomicEvidence(input.text);
  const scores = scoreEvidence(evidence, input.source_reliability);
  const eligibility = scores.economic.evidence_strength === 100 && (scores.economic.pain_score > 0 || scores.economic.demand_score > 0 || scores.economic.monetary_impact_score > 0 || scores.economic.solution_gap_score > 0);
  const unknowns = Object.entries(evidence).filter(([key, value]) => value === null || (key === "buying_intent" && !value) || (key === "urgency" && !value)).map(([key]) => key);
  const body = { service_version: SERVICE_VERSION, input_hash, evidence, scores, unknowns, eligibility: { economically_meaningful: eligibility, basis: "deterministic keyword and regex evidence only; this is not a fact finding or payment recommendation." }, fulfillment_id: `ful_${input_hash.slice(0, 24)}` };
  return { ...body, output_hash: await sha256(canonical(body)) };
}
