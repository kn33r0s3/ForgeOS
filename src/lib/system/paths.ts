/**
 * Possibility paths and progression derived from the person's own System
 * state plus the real public feed.
 *
 * Epistemic contract (mirrors the Universal Substrate TRUTH ladder):
 *   - Everything produced here is at most `possible`. A path is not an
 *     opportunity, a match is not demand, and nothing here is income.
 *   - Every path lists what is unknown and the smallest real next step.
 *   - No path invents a person, business, price, customer or outcome.
 */

import type { PublicFeedItem } from "@/lib/content";
import type { SystemGoal, SystemState } from "./state";

export type PathKind = "capability" | "resource" | "growth" | "service" | "context";

export type PossibilityPath = {
  id: string;
  kind: PathKind;
  title: string;
  why: string;
  unknowns: string[];
  nextStep: string;
  /** Internal link for the legitimate next step, if one exists. */
  href?: "/request" | "/providers" | "/discoveries" | "/feed" | "/system";
  epistemic: "possible";
  /** Which parts of the person's state produced this path (explainability). */
  from: string[];
};

type ResourceRule = {
  id: string;
  test: RegExp;
  title: (item: string) => string;
  why: string;
  unknowns: string[];
  nextStep: string;
};

/**
 * Resource → possible use. These are general, well-known value relations
 * (unused capacity → matching demand), phrased as possibilities only.
 */
const RESOURCE_RULES: ResourceRule[] = [
  {
    id: "vehicle",
    test: /\b(bike|motorbike|scooter|car|van|truck|tempo|vehicle|jeep|cycle)\b/i,
    title: (i) => `Your ${i} is transport capacity`,
    why: "Idle transport time can carry goods, parcels or people for others nearby.",
    unknowns: ["Local delivery demand near you", "Licence / insurance requirements", "Fuel cost vs. fare"],
    nextStep: "Describe the routes and hours you could cover; Hami keeps it as a stated capability.",
  },
  {
    id: "space",
    test: /\b(room|shop|shutter|space|land|garage|storage|godown|roof|terrace|field|plot)\b/i,
    title: (i) => `Your ${i} is unused capacity`,
    why: "Unused space can become storage, a workspace, a stall or growing area for someone who lacks it.",
    unknowns: ["Who nearby needs space", "Local rules on use", "A fair rate"],
    nextStep: "Note when and how the space is free so a real need can be matched to it.",
  },
  {
    id: "device",
    test: /\b(laptop|computer|pc|smartphone|phone|camera|printer|drone|internet|wifi)\b/i,
    title: (i) => `Your ${i} unlocks digital work`,
    why: "A connected device is the entry point to remote work, digital services and learning.",
    unknowns: ["Connection reliability", "Which digital skill fits you best"],
    nextStep: "Pick one digital capability to build first; Hami will surface relevant knowledge.",
  },
  {
    id: "tools",
    test: /\b(tools?|drill|sewing|machine|generator|pump|welding|ladder|kitchen|oven|equipment)\b/i,
    title: (i) => `Your ${i} is someone else's missing capability`,
    why: "Equipment you own but don't use daily can be rented or used to provide a service.",
    unknowns: ["Nearby demand", "Condition and safety", "Deposit / damage terms"],
    nextStep: "List the equipment's condition and availability as a stated resource.",
  },
  {
    id: "livestock_crops",
    test: /\b(cows?|buffalo|goats?|chickens?|poultry|crops?|vegetables?|fruit|milk|honey|tea|cardamom|farm)\b/i,
    title: (i) => `Your ${i} connects to local supply chains`,
    why: "Farm output and surplus can reach buyers, processors or collection centres beyond the nearest market.",
    unknowns: ["Current prices in nearby markets", "Transport to buyers", "Volume you can supply"],
    nextStep: "Record what you produce and when surplus appears so buyers and prices can be researched.",
  },
];

type GoalRule = {
  goal: SystemGoal;
  kind: PathKind;
  title: string;
  why: string;
  unknowns: string[];
  nextStep: string;
  href?: PossibilityPath["href"];
};

const GOAL_RULES: GoalRule[] = [
  {
    goal: "grow_skills",
    kind: "growth",
    title: "Find the smallest next capability",
    why: "The most valuable skill is usually the one closest to what you already do that opens paid work.",
    unknowns: ["Which skills are in demand where you are", "Free or low-cost ways to learn them"],
    nextStep: "Browse research Hami has gathered; add the skills you already have to sharpen this.",
    href: "/discoveries",
  },
  {
    goal: "find_services",
    kind: "service",
    title: "Check verified providers first",
    why: "Hami only lists providers that are publicly verified; none is shown if none is verified yet.",
    unknowns: ["Whether a verified provider covers your area yet"],
    nextStep: "Look at verified providers, or describe the need so Hami can look for one.",
    href: "/providers",
  },
  {
    goal: "start_or_grow_business",
    kind: "growth",
    title: "Describe the real problem your business solves",
    why: "A concrete, specific need is what Hami can research for demand, suppliers and customers.",
    unknowns: ["Who pays for this today", "What they pay", "What alternatives they use"],
    nextStep: "Share the need privately; it becomes a signal Hami investigates, not a public post.",
    href: "/request",
  },
  {
    goal: "find_work",
    kind: "capability",
    title: "Turn what you can do into a findable capability",
    why: "Work finds people whose capabilities, location and hours are known and specific.",
    unknowns: ["Nearby demand for your capabilities", "Typical rates"],
    nextStep: "Add capabilities and hours to your System; matching improves as they get specific.",
    href: "/system",
  },
];

function slug(s: string): string {
  return s.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "").slice(0, 40);
}

export function derivePaths(state: SystemState): PossibilityPath[] {
  const paths: PossibilityPath[] = [];
  const where = state.location?.value;
  const goals = new Set(state.goals.map((g) => g.value));

  // Resource → possible use (unused capacity → someone else's need).
  const usedRules = new Set<string>();
  for (const r of state.resources) {
    const rule = RESOURCE_RULES.find((rr) => rr.test.test(r.value) && !usedRules.has(rr.id));
    if (!rule) continue;
    usedRules.add(rule.id);
    paths.push({
      id: `resource:${rule.id}`,
      kind: "resource",
      title: rule.title(r.value),
      why: where ? `${rule.why} Near ${where}.` : rule.why,
      unknowns: rule.unknowns,
      nextStep: rule.nextStep,
      href: "/system",
      epistemic: "possible",
      from: [`resource: ${r.value}`],
    });
  }

  // Capability → someone else's problem solved.
  for (const c of state.capabilities.slice(0, 3)) {
    const earning = goals.has("earn_more") || goals.has("find_work");
    paths.push({
      id: `capability:${slug(c.value)}`,
      kind: "capability",
      title: `“${c.value}” can solve someone's problem`,
      why: earning
        ? "A capability becomes income when it meets a specific need, at a time and place that works."
        : "Capabilities you already have are the fastest route to useful work and trust.",
      unknowns: ["Who near you needs this now", "What they would pay", "Evidence of past work"],
      nextStep: "Keep a record of real work you complete; evidence is what turns a claim into trust.",
      href: "/system",
      epistemic: "possible",
      from: [`capability: ${c.value}`],
    });
  }

  // Capability × resource combination: the connection people often miss.
  const cap = state.capabilities[0];
  const res = state.resources[0];
  if (cap && res) {
    paths.push({
      id: `combo:${slug(cap.value)}:${slug(res.value)}`,
      kind: "capability",
      title: `${cap.value} + ${res.value}`,
      why: "Combining a skill with something you own often creates a service neither creates alone.",
      unknowns: ["Whether the combination fits local demand"],
      nextStep: "Describe the combined service in one sentence; Hami researches whether it is needed.",
      href: "/request",
      epistemic: "possible",
      from: [`capability: ${cap.value}`, `resource: ${res.value}`],
    });
  }

  for (const rule of GOAL_RULES) {
    if (!goals.has(rule.goal)) continue;
    paths.push({
      id: `goal:${rule.goal}`,
      kind: rule.kind,
      title: rule.title,
      why: rule.why,
      unknowns: rule.unknowns,
      nextStep: rule.nextStep,
      href: rule.href,
      epistemic: "possible",
      from: [`goal: ${rule.goal}`],
    });
  }

  if (goals.has("use_what_i_have") && state.resources.length === 0) {
    paths.push({
      id: "context:resources",
      kind: "context",
      title: "Tell Hami what you already have",
      why: "Things you own but rarely use — space, a vehicle, tools, a device — often have value to someone nearby.",
      unknowns: ["Your resources"],
      nextStep: "Add a few resources to your System.",
      href: "/system",
      epistemic: "possible",
      from: ["goal: use_what_i_have"],
    });
  }

  const seen = new Set<string>();
  return paths.filter((p) => (seen.has(p.id) ? false : (seen.add(p.id), true)));
}

/* ------------------------------------------------------------------ */
/* Relevance of real public feed items to this person                  */
/* ------------------------------------------------------------------ */

const STOP = new Set(
  "a an and are as at be by for from has have in is it of on or that the this to was were will with what who not no your you our can how".split(
    " ",
  ),
);

export function terms(text: string): Set<string> {
  const out = new Set<string>();
  for (const w of text.toLowerCase().split(/[^a-z0-9\u0900-\u097f]+/)) {
    if (w.length >= 3 && !STOP.has(w)) out.add(w);
  }
  return out;
}

export type RelevantItem = { item: PublicFeedItem; shared: string[] };

/**
 * Transparent keyword relevance: an item is relevant only when it shares
 * concrete words with the person's own stated capabilities, resources,
 * location or constraints. The shared words are returned so the UI can
 * say exactly why — never a hidden score.
 */
export function relevantFeed(state: SystemState, items: PublicFeedItem[]): RelevantItem[] {
  const mine = new Set<string>();
  for (const k of [...state.capabilities, ...state.resources, ...state.constraints]) {
    for (const t of terms(k.value)) mine.add(t);
  }
  if (state.location) for (const t of terms(state.location.value)) mine.add(t);
  if (mine.size === 0) return [];
  const out: RelevantItem[] = [];
  for (const item of items) {
    const words = terms(`${item.title} ${item.summary} ${item.location ?? ""}`);
    const shared = [...mine].filter((t) => words.has(t));
    if (shared.length) out.push({ item, shared: shared.slice(0, 4) });
  }
  return out.sort((a, b) => b.shared.length - a.shared.length);
}

/* ------------------------------------------------------------------ */
/* Progression: grounded in real state, never XP                       */
/* ------------------------------------------------------------------ */

export type StageId = "context" | "capabilities" | "action" | "evidence";

export type Stage = {
  id: StageId;
  label: string;
  meaning: string;
  reached: boolean;
  /** What would move this stage forward. */
  requirement: string;
  /** Stages that can only be reached through server-side evidence. */
  evidenceGated: boolean;
};

export function deriveStages(
  state: SystemState,
  opts: { recordedRequests: number } = { recordedRequests: 0 },
): Stage[] {
  const context = Boolean(state.location && state.time && state.goals.length);
  const caps = state.capabilities.length > 0 && state.resources.length > 0;
  return [
    {
      id: "context",
      label: "Situation known",
      meaning: "Hami knows where you are, your time and what you want.",
      reached: context,
      requirement: "Location, weekly time and at least one goal.",
      evidenceGated: false,
    },
    {
      id: "capabilities",
      label: "Gear mapped",
      meaning: "Your capabilities and resources are known, so paths can be found.",
      reached: caps,
      requirement: "At least one capability and one resource.",
      evidenceGated: false,
    },
    {
      id: "action",
      label: "First real step",
      meaning: "You took a real step through Hami — a need shared or a request sent.",
      reached: opts.recordedRequests > 0,
      requirement: "Share a real need or send a request to a verified provider.",
      evidenceGated: false,
    },
    {
      id: "evidence",
      label: "Evidenced outcome",
      meaning: "A real result backed by evidence: completed work, a verified payment.",
      reached: false,
      requirement: "Only verified evidence can reach this stage. It cannot be self-declared.",
      evidenceGated: true,
    },
  ];
}
