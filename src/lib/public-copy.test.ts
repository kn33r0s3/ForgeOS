import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { describe, it } from "node:test";

/**
 * Public copy may not contain claims the API doesn't back.
 *
 * Every displayed item on the public site must come from the API with a
 * source and a truth label. This test fails if a public route:
 *  - imports a hand-written data module (findings baked into the bundle),
 *  - contains claim phrases (results, guarantees, social proof) that no
 *    API backs, or
 *  - renders engine data without importing the API module that carries
 *    its source and truth label.
 */
const PUBLIC_ROUTES: Array<{ path: string; file: string }> = [
  { path: "/", file: "src/routes/index.tsx" },
  { path: "/needs", file: "src/routes/needs.tsx" },
  { path: "/unknowns", file: "src/routes/unknowns.tsx" },
  { path: "/about", file: "src/routes/about.tsx" },
];

// Hand-written data modules: findings baked into the bundle. Public
// routes must read from the API instead. Matched as full import paths.
const BANNED_IMPORTS = ['@/lib/unknowns"', "@/lib/unknowns'", '@/lib/needs"', "@/lib/needs'"];

// Claim phrases no API backs. Honest-state phrases ("no merchants served
// yet", "pre-revenue", "no week has run yet") are deliberately absent.
const CLAIM_PATTERNS: RegExp[] = [
  /\bproven\b/i,
  /guaranteed/i,
  /trusted by/i,
  /\b\d+\+?\s+merchants\s+served/i,
  /\bwe('|’ve| have) recovered\b/i,
  /Rs\.?\s?\d[\d,]*\s+(recovered|earned|paid)/i,
  /₨\s?\d[\d,]*\s+(recovered|earned|paid)/i,
  /Nepal first/i,
  /sign up.*free trial/i,
];

// Routes that render engine data must import the API module carrying
// source + truth label.
const API_BACKED: Array<{ file: string; apiModule: string }> = [
  { file: "src/routes/unknowns.tsx", apiModule: "@/lib/unknowns-api" },
  { file: "src/routes/discoveries.tsx", apiModule: "loadDiscoveries" },
];

function read(file: string): string {
  return readFileSync(new URL(`../../${file}`, import.meta.url), "utf8");
}

describe("public copy is backed by the API", () => {
  for (const route of PUBLIC_ROUTES) {
    it(`${route.path}: no hand-written data imports`, () => {
      const src = read(route.file);
      for (const banned of BANNED_IMPORTS) {
        assert.ok(
          !src.includes(banned),
          `${route.path} imports hand-written data (${banned}) — read from the API instead`,
        );
      }
    });

    it(`${route.path}: no unbacked claim phrases`, () => {
      const src = read(route.file);
      for (const pattern of CLAIM_PATTERNS) {
        assert.ok(
          !pattern.test(src),
          `${route.path} contains an unbacked claim matching ${pattern}`,
        );
      }
    });
  }

  for (const entry of API_BACKED) {
    it(`${entry.file}: engine data comes through its API module`, () => {
      const src = read(entry.file);
      assert.ok(
        src.includes(entry.apiModule),
        `${entry.file} renders engine data without ${entry.apiModule} (source + truth label)`,
      );
    });
  }
});

describe("homepage contract", () => {
  const home = () => read("src/routes/index.tsx").replace(/\s+/g, " ");
  const header = () => read("src/components/layout/site-header.tsx");
  const footer = () => read("src/components/layout/site-footer.tsx");
  const surfaces = () => home() + header() + footer();

  it("1. carries the Hami identity headline, in English and Nepali", () => {
    const src = home();
    assert.match(
      src,
      /Hami is a living system that understands what people need and turns understanding into real value/,
    );
    assert.match(
      src,
      /\u0939\u093e\u092e\u0940 \u090f\u0909\u091f\u093e \u091c\u0940\u0935\u093f\u0924 \u092a\u094d\u0930\u0923\u093e\u0932\u0940 \u0939\u094b/,
    );
    const h1 = src.match(/<h1[^>]*>(.*?)<\/h1>/)?.[1] ?? "";
    assert.ok(!/slow reply|inbox|sale/i.test(h1), `h1 is the wedge, not Hami: ${h1}`);
  });

  it("2. carries the Nepal/global identity", () => {
    const src = home();
    assert.match(src, /Built in Kathmandu/);
    assert.match(src, /Serving everywhere equally/);
    assert.match(
      src,
      /\u0915\u093e\u0920\u092e\u093e\u0921\u094c\u0902\u092e\u093e \u092c\u0928\u0947\u0915\u094b/,
    );
  });

  it("3. shows the four plain lines, in English and Nepali", () => {
    const src = home();
    for (const line of [
      "Observes",
      "Keeps evidence and uncertainty",
      "Acts only when authorized",
      "Learns from outcomes",
    ]) {
      assert.ok(src.includes(line), `missing plain line: ${line}`);
    }
    assert.match(src, /These capacities can inform one another/);
    assert.match(src, /no fixed sequence/);
  });

  it("4. explains Hami's open-ended relationship with reality", () => {
    const src = home();
    for (const concept of [
      "real situations",
      "Needs",
      "unused capability",
      "opportunities",
      "mismatches",
      "constraints",
      "relationships",
      "resources",
      "problems worth solving",
      "useful outcome",
      "evidence",
      "uncertainty",
      "authorized",
      "actual outcomes",
    ]) {
      assert.ok(src.includes(concept), `missing system concept: ${concept}`);
    }
    assert.match(src, /not discoveries claimed here/);
  });

  it("5. keeps Experiment 1 as one small, not-started current investigation", () => {
    const src = home();
    const currentActivityStart = src.indexOf("function CurrentActivity");
    const currentActivityEnd = src.indexOf("function HonestStatus", currentActivityStart);
    assert.ok(currentActivityStart >= 0 && currentActivityEnd > currentActivityStart);
    const currentActivity = src.slice(currentActivityStart, currentActivityEnd);
    assert.match(currentActivity, /Currently exploring/);
    assert.match(currentActivity, /One proposed investigation · not started/);
    assert.match(currentActivity, /Experiment 1/);
    assert.match(currentActivity, /No seller has agreed/);
    assert.match(currentActivity, /not Hami's identity or a live offer/);
    assert.match(currentActivity, /to="\/needs"/);
    assert.doesNotMatch(currentActivity, /<h1|<Button|\/prototype\/inbox|Try the free inbox tool/);
    assert.match(
      src,
      /<Identity \/> <FourLines \/> <SystemScope \/> <RecordedObservations \/> <CurrentActivity \/> <HonestStatus \/>/,
    );
  });

  it("keeps the inbox prototype out of primary navigation and labels its footer link TEST-only", () => {
    assert.doesNotMatch(header(), /Inbox tool|\/prototype\/inbox/);
    assert.match(footer(), /Inbox prototype \(TEST only\)/);
    assert.match(footer(), /to: "\/prototype\/inbox"/);
  });

  it("6. does not position Hami as an inbox, reply service, seller business, or fixed vertical", () => {
    const src = home();
    const primarySystemCopy = src.slice(0, src.indexOf("function CurrentActivity"));
    const headline = primarySystemCopy.match(/<h1[^>]*>(.*?)<\/h1>/)?.[1] ?? "";
    assert.match(headline, /Hami is a living system/);
    assert.doesNotMatch(headline, /slow reply|inbox|seller|shop|business|customer support|sale/i);
    assert.doesNotMatch(
      primarySystemCopy,
      /inbox|seller|shop|business(?:es)?|software|services?|customer support|lead[- ]generation|commerce|for online sellers|for businesses|commerce platform|seller reply service/i,
    );
    assert.doesNotMatch(
      primarySystemCopy,
      /Hami\s+(?:is designed|exists|operates|works)\s+for\s+\w+/i,
      "Hami must not be described as serving one fixed vertical or customer type",
    );
    const reductions = [
      /Hami is a (tool|inbox|saas|chatbot|calculator|reply service)\b/i,
      /Hami is an (inbox|app|product|chatbot)\b/i,
      /Hami is just /i,
      /Hami is merely /i,
      /lead[- ]generation/i,
    ];
    for (const pattern of reductions) {
      assert.ok(!pattern.test(src), `homepage reduces Hami: ${pattern}`);
    }
    assert.match(primarySystemCopy, /no fixed sequence or single product defines the system/);
  });

  it("7. removed surface stays removed", () => {
    const blob = surfaces();
    const banned = [
      "Sign in",
      "Explore the network",
      "Online inquiries are not open yet.",
      "Opening your System",
      "Contact mailbox pending",
      "Domain pending verification",
      "Edit my context",
      "Share a need",
      "candidate notebook",
      "Nepal-first",
      "Submit a need",
      "mailbox pending",
      "pending verification",
    ];
    for (const phrase of banned) {
      assert.ok(!blob.includes(phrase), `banned surface reappeared: ${phrase}`);
    }
    assert.ok(!blob.includes('"/feed"'), "/feed is linked from a public surface");
  });

  it("8. public observations on the homepage are loaded from recorded API data", () => {
    const src = read("src/routes/index.tsx").replace(/\s+/g, " ");
    assert.ok(
      src.includes("loadDiscoveries"),
      "homepage must use the existing observations API loader",
    );
    assert.match(src, /Nothing is recorded in this public observation record yet/);
    assert.match(src, /The public record is unavailable right now/);
    assert.match(src, /item\.source/);
    assert.match(src, /item\.epistemic_state/);
    assert.match(src, /item\.canonical_url/);
    assert.ok(
      !/const FINDINGS|fetchUnknowns|u\.question/.test(src),
      "homepage must not substitute questions as findings",
    );
  });

  it("9. no keyword-bag / hypothesis shortcut", () => {
    const src = read("src/routes/index.tsx");
    assert.ok(!/keyword/i.test(src), "keyword-bag language in homepage");
  });

  it("10. honest status line remains present without seller-first framing", () => {
    const src = home();
    assert.match(src, /Honest status/i);
    assert.match(src, /pre-revenue/i);
    assert.match(src, /Experiment 1 remains proposed/);
    assert.match(src, /no participants or results to report/);
    assert.doesNotMatch(src.slice(src.indexOf("function HonestStatus")), /seller|shop|inbox/i);
  });

  it("metadata titles all say Hami", () => {
    const src = home();
    assert.match(src, /\{\s*title:\s*"Hami"\s*\}/);
    assert.match(src, /"og:title",\s*content:\s*"Hami"/);
    assert.match(src, /"apple-mobile-web-app-title",\s*content:\s*"Hami"/);
  });

  it("footer says Built in Kathmandu", () => {
    assert.match(footer(), /Built in Kathmandu/);
  });

  it("what-we-learned renders engine data through the API module, nothing hand-written", () => {
    const src = read("src/routes/what-we-learned.tsx");
    assert.ok(
      src.includes("@/lib/unknowns-api"),
      "what-we-learned must import the engine API module",
    );
    assert.match(src, /fetchUnknowns/);
    assert.match(src, /unavailable right now/i);
    assert.match(src, /Nothing recorded yet/);
    assert.match(src, /will not invent findings/i);
  });
});
