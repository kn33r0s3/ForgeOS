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
  { file: "src/routes/unknowns.tsx", apiModule: "loadPublicUnknowns" },
  { file: "src/routes/discoveries.tsx", apiModule: "loadDiscoveries" },
  { file: "src/routes/index.tsx", apiModule: "loadUnknownsSummary" },
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

  it("1. hero carries the design headline and Hami identity, in English and Nepali", () => {
    const src = home();
    assert.match(src, /Discover what matters/);
    assert.match(src, /Understand it/);
    assert.match(src, /Act on it/);
    assert.match(
      src,
      /Hami is a living system that understands what people need and turns understanding into real value/,
    );
    assert.match(
      src,
      /\u0939\u093e\u092e\u0940 \u090f\u0909\u091f\u093e \u091c\u0940\u0935\u093f\u0924 \u092a\u094d\u0930\u0923\u093e\u0932\u0940 \u0939\u094b/,
    );
    // Reality loop SVG present
    assert.match(src, /RealityLoop/);
    assert.match(src, /New reality/);
  });

  it("2. carries the Kathmandu/global identity without Nepal-first framing", () => {
    const src = home();
    assert.match(src, /Built in Kathmandu/);
    assert.match(src, /Serving everywhere equally/);
    assert.doesNotMatch(src, /Nepal-first|Nepal first/i);
  });

  it("3. shows the six primitives with one-line definitions", () => {
    const src = home();
    for (const p of ["Entity", "Relation", "Event", "Evidence", "Capability", "Action"]) {
      assert.ok(src.includes(p), `missing primitive: ${p}`);
    }
  });

  it("4. power of the unknown uses engine states from the API", () => {
    const src = home();
    assert.match(src, /The power of the unknown/);
    assert.match(src, /loadUnknownsSummary/);
    for (const s of [
      "UNKNOWN",
      "HYPOTHESIZED",
      "TESTED",
      "SUPPORTED",
      "CONTRADICTED",
      "BLOCKED_BY_MISSING_ACCESS",
    ]) {
      assert.ok(src.includes(s), `missing state: ${s}`);
    }
    // Never ship bracketed placeholders
    assert.doesNotMatch(src, /\\[count from API\\]/);
  });

  it("keeps the inbox prototype out of primary navigation and labels its footer link TEST-only", () => {
    assert.doesNotMatch(header(), /Inbox tool|\/prototype\/inbox/);
    assert.match(footer(), /Inbox prototype \(TEST only\)/);
    assert.match(footer(), /to: "\/prototype\/inbox"/);
  });

  it("6. does not position Hami as an inbox, reply service, seller business, or fixed vertical", () => {
    const src = home();
    // Identity sentence present (in hero body, per design)
    assert.match(src, /Hami is a living system that understands what people need/);
    // H1 is the design headline, not the wedge
    const headline = src.match(/<h1[^>]*>([\s\S]*?)<\/h1>/)?.[1] ?? "";
    assert.doesNotMatch(headline, /slow reply|inbox|seller|shop|business|customer support|sale/i);
    // No vertical-specific positioning in hero
    const heroEnd = src.indexOf("function PrimitivesStrip");
    const hero = src.slice(0, heroEnd > 0 ? heroEnd : src.length);
    assert.doesNotMatch(
      hero,
      /for online sellers|for businesses|commerce platform|seller reply service|lead[- ]generation/i,
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
  });


  it("7. removed surface stays removed", () => {
    const blob = surfaces();
    const banned = [
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

  it("8. what we have learned loads from the API with honest empty states", () => {
    const src = read("src/routes/index.tsx").replace(/\\s+/g, " ");
    assert.ok(
      src.includes("loadDiscoveries"),
      "homepage must use the existing observations API loader",
    );
    assert.match(src, /What we have learned/);
    assert.match(src, /Nothing recorded yet/);
    assert.match(src, /Findings unavailable right now/);
    assert.match(src, /item\\.source/);
    assert.match(src, /item\\.canonical_url/);
    assert.match(src, /Observed/);
    assert.match(src, /Hypothesis/);
    assert.match(src, /Supported/);
  });


  it("9. no keyword-bag / hypothesis shortcut", () => {
    const src = read("src/routes/index.tsx");
    assert.ok(!/keyword/i.test(src), "keyword-bag language in homepage");
  });

  it("10. footer carries honest status without seller-first framing", () => {
    const src = home();
    assert.match(src, /Honest status/i);
    assert.match(src, /pre-revenue/i);
    assert.match(src, /Experiment 1 remains proposed/);
    assert.match(src, /no participants or results to report/);
    assert.doesNotMatch(src, /mailto:|tel:/);
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
  it("5. very big very small: Experiment 1 is step 1, rest when earned", () => {
    const src = read("src/routes/about.tsx");
    assert.match(src, /Very big, very small/);
    assert.match(src, /One seller, one week/);
    assert.match(src, /Experiment 1/);
    assert.match(src, /No seller has agreed/);
    assert.match(src, /when earned/);
    assert.match(src, /Try the free inbox tool/);
    assert.match(src, /\/prototype\/inbox/);
    assert.doesNotMatch(src, /\[when earned\]/);
  });

});

describe("information architecture", () => {
  const home = () => read("src/routes/index.tsx");
  const navRoutes = ["/", "/discoveries", "/unknowns", "/experiments", "/about"];

  it("every homepage preview section links to a real nav route", () => {
    const src = home();
    for (const route of ["/discoveries", "/unknowns", "/experiments"]) {
      assert.ok(
        src.includes(`to="${route}"`),
        `homepage preview missing link to ${route}`,
      );
    }
    assert.ok(src.includes('to="/about"'), "homepage missing link to /about");
    // All preview links must be in NAV
    const nav = read("src/lib/content.ts");
    for (const route of navRoutes) {
      assert.ok(nav.includes(`to: "${route}"`), `NAV missing ${route}`);
    }
  });

  it("homepage has no content of its own — only previews", () => {
    const src = home();
    // Primitives strip moved to /about
    assert.doesNotMatch(src, /Six primitives|PRIMITIVES/);
    // Climb moved to /about
    assert.doesNotMatch(src, /Very big, very small|CLIMB_STEPS/);
    // No power-of-unknown counts (not a preview)
    assert.doesNotMatch(src, /The power of the unknown|loadUnknownsSummary/);
  });

  it("no homepage data string not served by that page's API", () => {
    const src = home();
    // Findings preview uses loadDiscoveries (same as /discoveries)
    assert.match(src, /loadDiscoveries/);
    // Unknowns preview uses loadPublicUnknowns (same as /unknowns)
    assert.match(src, /loadPublicUnknowns/);
    // Experiments uses the shared EXPERIMENTS data
    assert.match(src, /EXPERIMENTS/);
    // No hardcoded finding/unknown text on homepage
    assert.doesNotMatch(src, /const FINDINGS|const UNKNOWNS/);
  });
});
