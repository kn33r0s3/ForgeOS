/**
 * The person's Hami System state ("gear").
 *
 * Ownership rule: guest state stays in tab-scoped session storage. Account
 * state is persisted through owner-scoped server functions, never this module.
 *
 * Truth rule: every value records how Hami knows it. A value the person
 * typed is `stated`; it is never upgraded to `verified` on the client.
 * Verification can only come from server-side evidence.
 */

export type Provenance = "stated" | "inferred" | "verified";

export type Known<T> = {
  value: T;
  provenance: Provenance;
  updatedAt: string;
};

export type TimeAvailability = "under_5h" | "5_to_15h" | "15_to_30h" | "full_time";

export type SystemGoal =
  | "earn_more"
  | "find_work"
  | "grow_skills"
  | "start_or_grow_business"
  | "use_what_i_have"
  | "find_services";

export type SystemState = {
  version: 1;
  location?: Known<string>;
  time?: Known<TimeAvailability>;
  capabilities: Known<string>[];
  resources: Known<string>[];
  goals: Known<SystemGoal>[];
  constraints: Known<string>[];
  createdAt: string;
  updatedAt: string;
};

export const STORAGE_KEY = "hami.guest-system.v2";
export const LEGACY_STORAGE_KEY = "hami.system.v1";

export const TIME_LABELS: Record<TimeAvailability, string> = {
  under_5h: "Under 5 hours a week",
  "5_to_15h": "5–15 hours a week",
  "15_to_30h": "15–30 hours a week",
  full_time: "Full time",
};

export const GOAL_LABELS: Record<SystemGoal, string> = {
  earn_more: "Earn more",
  find_work: "Find work",
  grow_skills: "Grow a useful skill",
  start_or_grow_business: "Start or grow a business",
  use_what_i_have: "Use what I already have",
  find_services: "Find a service I need",
};

export function emptyState(now = new Date().toISOString()): SystemState {
  return {
    version: 1,
    capabilities: [],
    resources: [],
    goals: [],
    constraints: [],
    createdAt: now,
    updatedAt: now,
  };
}

export function stated<T>(value: T, now = new Date().toISOString()): Known<T> {
  return { value, provenance: "stated", updatedAt: now };
}

const MAX_ITEM = 80;
const MAX_ITEMS = 24;

/** Normalize a free-text item: trim, collapse whitespace, cap length. */
export function cleanItem(raw: string): string {
  return raw.replace(/\s+/g, " ").trim().slice(0, MAX_ITEM);
}

/** Split comma/newline separated input into unique, cleaned items. */
export function parseList(raw: string): string[] {
  const seen = new Set<string>();
  const out: string[] = [];
  for (const part of raw.split(/[,\n]/)) {
    const item = cleanItem(part);
    const key = item.toLowerCase();
    if (!item || seen.has(key)) continue;
    seen.add(key);
    out.push(item);
    if (out.length >= MAX_ITEMS) break;
  }
  return out;
}

const GOALS = new Set<string>(Object.keys(GOAL_LABELS));
const TIMES = new Set<string>(Object.keys(TIME_LABELS));
const PROVENANCE = new Set<string>(["stated", "inferred", "verified"]);

function isKnown(value: unknown): value is Known<unknown> {
  if (!value || typeof value !== "object") return false;
  const v = value as Record<string, unknown>;
  return (
    "value" in v &&
    typeof v.updatedAt === "string" &&
    typeof v.provenance === "string" &&
    PROVENANCE.has(v.provenance)
  );
}

/**
 * A client can never hold verified evidence: anything read back from local
 * storage claiming `verified` is downgraded to `stated`.
 */
function asStated<T>(k: Known<T>): Known<T> {
  return k.provenance === "verified" ? { ...k, provenance: "stated" } : k;
}

function knownStrings(value: unknown): Known<string>[] {
  if (!Array.isArray(value)) return [];
  return value
    .filter(isKnown)
    .filter((k) => typeof k.value === "string" && cleanItem(k.value as string))
    .map((k) => asStated({ ...(k as Known<string>), value: cleanItem(k.value as string) }))
    .slice(0, MAX_ITEMS);
}

/** Parse untrusted stored JSON into a valid state, dropping anything malformed. */
export function parseState(raw: string | null): SystemState | null {
  if (!raw) return null;
  let data: unknown;
  try {
    data = JSON.parse(raw);
  } catch {
    return null;
  }
  if (!data || typeof data !== "object") return null;
  const d = data as Record<string, unknown>;
  if (d.version !== 1) return null;
  const base = emptyState(typeof d.createdAt === "string" ? d.createdAt : undefined);
  const location =
    isKnown(d.location) && typeof d.location.value === "string" && cleanItem(d.location.value)
      ? asStated({ ...(d.location as Known<string>), value: cleanItem(d.location.value) })
      : undefined;
  const time =
    isKnown(d.time) && typeof d.time.value === "string" && TIMES.has(d.time.value)
      ? asStated(d.time as Known<TimeAvailability>)
      : undefined;
  const goals = Array.isArray(d.goals)
    ? d.goals
        .filter(isKnown)
        .filter((k) => typeof k.value === "string" && GOALS.has(k.value))
        .map((k) => asStated(k as Known<SystemGoal>))
    : [];
  return {
    ...base,
    location,
    time,
    capabilities: knownStrings(d.capabilities),
    resources: knownStrings(d.resources),
    goals,
    constraints: knownStrings(d.constraints),
    updatedAt: typeof d.updatedAt === "string" ? d.updatedAt : base.updatedAt,
  };
}

export function loadState(storage: Pick<Storage, "getItem"> | undefined): SystemState | null {
  if (!storage) return null;
  try {
    return parseState(storage.getItem(STORAGE_KEY));
  } catch {
    return null;
  }
}

export function saveState(storage: Pick<Storage, "setItem"> | undefined, state: SystemState): boolean {
  if (!storage) return false;
  try {
    storage.setItem(STORAGE_KEY, JSON.stringify(state));
    return true;
  } catch {
    return false;
  }
}

export function clearState(storage: Pick<Storage, "removeItem"> | undefined): void {
  try {
    storage?.removeItem(STORAGE_KEY);
  } catch {
    /* ignore */
  }
}

export function loadGuestState(
  sessionStorage: Pick<Storage, "getItem" | "setItem"> | undefined,
  localStorage: Pick<Storage, "getItem" | "removeItem"> | undefined,
): SystemState | null {
  const temporary = loadState(sessionStorage);
  let legacy: SystemState | null = null;
  try {
    legacy = parseState(localStorage?.getItem(LEGACY_STORAGE_KEY) ?? null);
  } catch {
    legacy = null;
  }
  try {
    localStorage?.removeItem(LEGACY_STORAGE_KEY);
  } catch {
    // Storage may be unavailable; the legacy value is never uploaded here.
  }
  if (temporary) return temporary;
  if (!legacy) return null;
  saveState(sessionStorage, legacy);
  return legacy;
}

export function clearGuestState(
  sessionStorage: Pick<Storage, "removeItem"> | undefined,
  localStorage: Pick<Storage, "removeItem"> | undefined,
): void {
  clearState(sessionStorage);
  try {
    localStorage?.removeItem(LEGACY_STORAGE_KEY);
  } catch {
    /* ignore */
  }
}

export function hasAnyState(state: SystemState | null): state is SystemState {
  return Boolean(
    state &&
      (state.location ||
        state.time ||
        state.capabilities.length ||
        state.resources.length ||
        state.goals.length),
  );
}
