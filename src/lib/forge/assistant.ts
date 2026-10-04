/**
 * ForgeBot v0 — the operator's assistant.
 *
 * Two jobs, both real:
 *   1. verifyRound() — check the operator's round findings through the
 *      evidence gate BEFORE anything is banked. The assistant never lets
 *      an ungated claim through, no matter who found it.
 *   2. ripenessQueue() + isAngleTried() — say what's ripest to investigate
 *      next, and refuse repeated angles.
 *
 * Later: the assistant runs rounds itself (competitor), then better.
 * Now: it assists. Every function here is used by the operator today.
 */

import { EvidenceGateError, verifyClaim, type Claim } from "../evidence.ts";
import { discoveryUnknowns } from "../unknowns.ts";
import { triedAngles } from "./tried-angles.ts";
import { valueOf, valueTier } from "./value-tiers.ts";
import type { ValueTier } from "./value.ts";

export interface RoundFinding extends Claim {
  /** Unknowns this finding addresses, or would create. */
  unknownIds: string[];
}

export interface RoundVerdict {
  verified: RoundFinding[];
  rejected: Array<{ finding: RoundFinding; reason: string }>;
}

/**
 * Gate a round's findings before banking. One bad finding fails only
 * itself here (the batch gate `verifyAll` is stricter) — but nothing
 * rejected gets banked. Returns the verdict; the caller banks only
 * `verified`.
 */
export function verifyRound(findings: RoundFinding[]): RoundVerdict {
  const verdict: RoundVerdict = { verified: [], rejected: [] };
  for (const finding of findings) {
    if (!Array.isArray(finding.unknownIds) || finding.unknownIds.length === 0) {
      verdict.rejected.push({
        finding,
        reason: "finding addresses no unknown — every finding must move the map",
      });
      continue;
    }
    try {
      verifyClaim(finding);
      verdict.verified.push(finding);
    } catch (e) {
      verdict.rejected.push({
        finding,
        reason: e instanceof EvidenceGateError ? e.message : "unknown gate failure",
      });
    }
  }
  return verdict;
}

export type Ripeness = "now" | "needs-human";

export interface RipeAngle {
  id: string;
  question: string;
  cheapestTest: string;
  stakes: string;
  round: number;
  ripeness: Ripeness;
  valueTier: ValueTier;
  valueWhy: string;
}

const HUMAN_GATED = /five conversations|ask [a-z]+ owners|ask \d+|a human|in person/i;

/**
 * What's ripest to investigate next: value first, then doability.
 * Open unknowns ranked by value tier (money-close before enablers before
 * understanding), desk-doable now before human-gated ones, oldest first
 * within each group. Value is the method — effort-ordering without
 * value-ordering is just motion.
 */
export function ripenessQueue(limit = 10): RipeAngle[] {
  const open = discoveryUnknowns.filter((u) => u.state === "unknown");
  const ranked: RipeAngle[] = open.map((u) => ({
    id: u.id,
    question: u.question,
    cheapestTest: u.cheapestTest,
    stakes: u.stakes,
    round: u.round,
    ripeness: HUMAN_GATED.test(u.cheapestTest) ? "needs-human" : "now",
    valueTier: valueTier(u.id),
    valueWhy: valueOf(u.id).why,
  }));
  ranked.sort((a, b) => {
    if (a.valueTier !== b.valueTier) return b.valueTier - a.valueTier;
    if (a.ripeness !== b.ripeness) return a.ripeness === "now" ? -1 : 1;
    return a.round - b.round;
  });
  return ranked.slice(0, limit);
}

const STOPWORDS = new Set(
  "the,a,an,of,to,in,on,for,and,or,what,how,does,do,is,are,was,were,be,been,by,with,from,that,this,these,those,it,its,as,at,which,who,whom,whose,when,where,why,not,no,yes,if,then,than,so,such,into,over,after,before,between,one,two,three".split(
    ",",
  ),
);

function keywords(text: string): Set<string> {
  return new Set(
    text
      .toLowerCase()
      .replace(/[^a-z0-9\s]/g, " ")
      .split(/\s+/)
      .filter((w) => w.length > 2 && !STOPWORDS.has(w)),
  );
}

/**
 * Refuse repeated angles. A proposed angle is "tried" if it shares at
 * least two significant keywords with any tried angle — the loop must
 * keep moving to new ground, never re-till the same field.
 */
export function isAngleTried(proposed: string): boolean {
  const words = keywords(proposed);
  if (words.size === 0) return false;
  for (const tried of triedAngles) {
    const triedWords = keywords(tried.angle);
    let overlap = 0;
    for (const w of words) {
      if (triedWords.has(w) && ++overlap >= 2) return true;
    }
  }
  return false;
}
