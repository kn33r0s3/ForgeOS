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
  { path: "/discoveries", file: "src/routes/discoveries.tsx" },
  { path: "/opportunities", file: "src/routes/opportunities.tsx" },
];

// Hand-written data modules: findings baked into the bundle. Public
// routes must read from the API instead. Matched as full import paths.
const BANNED_IMPORTS = ["@/lib/unknowns\"", "@/lib/unknowns'", "@/lib/needs\"", "@/lib/needs'"];

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
    assert.match(src, /\u0939\u093e\u092e\u0940 \u090f\u0909\u091f\u093e \u091c\u0940\u0935\u093f\u0924 \u092a\u094d\u0930\u0923\u093e\u0932\u0940 \u0939\u094b/);
    const h1 = src.match(/<h1[^>]*>(.*?)<\/h1>/)?.[1] ?? "";
    assert.ok(!/slow reply|inbox|sale/i.test(h1), `h1 is the wedge, not Hami: ${h1}`);
  });

  it("2. carries the Nepal/global identity", () => {
    const src = home();
    assert.match(src, /Built in Kathmandu/);
    assert.match(src, /Serving everywhere equally/);
    assert.match(src, /\u0915\u093e\u0920\u092e\u093e\u0921\u094c\u0902\u092e\u093e \u092c\u0928\u0947\u0915\u094b/);
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
    const identitySection = src.split("One bounded experiment")[0];
    assert.ok(
      !/ENTITY|RELATION|CAPABILITY/.test(identitySection),
      "implementation terminology leaked into the identity section",
    );
  });

  it("4. presents Experiment 1 as a subordinate hypothesis that has not started", () => {
    const src = home();
    assert.match(src, /Experiment 1/);
    assert.match(src, /A hypothesis inside Hami/);
    assert.match(src, /No seller has agreed to participate/);
    assert.match(src, /no experiment week has run/i);
    assert.match(src, /no upfront[\s\S]*attribute/i);
  });

  it("5. links to the experiment scope, not the local prototype", () => {
    const src = home();
    assert.match(src, /to="\/needs"/);
    assert.match(src, /Read the Experiment 1 scope/);
    assert.doesNotMatch(src, /\/prototype\/inbox|free inbox tool/i);
  });

  it("6. never implies Hami is merely a reply service, inbox tool, SaaS, chatbot, or lead-gen product", () => {
    const src = home();
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
      "Sign in",
      "Explore the network",
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
    assert.ok(!blob.includes('"/prototype/inbox"'), "local prototype is linked from a primary public surface");
    assert.ok(!blob.includes("Inbox tool"), "Hami is not labelled as an inbox tool");
  });

  it("8. open questions on the homepage are API-backed, not hand-written findings", () => {
    const src = read("src/routes/index.tsx").replace(/\s+/g, " ");
    assert.ok(src.includes("@/lib/unknowns-api"), "homepage must use the engine API module");
    assert.match(src, /fetchUnknowns/);
    assert.match(src, /No open questions are recorded yet/);
    assert.match(src, /These are questions, not findings or answers/);
    assert.match(src, /will not invent them/);
    assert.ok(!/const FINDINGS/.test(src), "hand-written findings dataset in homepage");
    assert.match(src, /to="\/unknowns"/);
  });

  it("9. no keyword-bag / hypothesis shortcut", () => {
    const src = read("src/routes/index.tsx");
    assert.ok(!/keyword/i.test(src), "keyword-bag language in homepage");
  });

  it("10. honest status line says the experiment has not started", () => {
    const src = home();
    assert.match(src, /Honest status/i);
    assert.match(src, /pre-revenue/i);
    assert.match(src, /no seller has agreed to participate/i);
    assert.match(src, /Experiment 1 has not started/i);
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

  it("keeps the legacy learning URL as a redirect to the canonical open-questions route", () => {
    const src = read("src/routes/what-we-learned.tsx");
    assert.match(src, /redirect\(\{ to: "\/unknowns" \}\)/);
    assert.doesNotMatch(src, /fetchUnknowns|What we've learned/);
  });

  it("keeps the prototype explicitly TEST-only and out of search indexing", () => {
    const prototype = read("src/routes/prototype.inbox.tsx").replace(/\s+/g, " ");
    assert.match(prototype, /name: "robots", content: "noindex, nofollow"/);
    assert.match(prototype, /TEST only — not a live product or evidence/);
    assert.match(prototype, /never count as real inquiries, recovered sales, customers, or revenue/);
  });

  it("does not claim Hami serves only Nepal in structured metadata", () => {
    assert.doesNotMatch(read("src/routes/__root.tsx"), /areaServed:\s*"NP"/);
  });

  it("exposes the system, evidence, and experiment—not a product prototype—in main navigation", () => {
    const content = read("src/lib/content.ts");
    assert.match(content, /label: "The system", to: "\/about"/);
    assert.match(content, /label: "Public record", to: "\/discoveries"/);
    assert.match(content, /label: "Experiment 1", to: "\/needs"/);
    assert.doesNotMatch(content, /label: "Inbox tool"|to: "\/prototype\/inbox"/);
    assert.match(header(), /aria-expanded=\{open\}/);
    assert.match(header(), /aria-controls="mobile-navigation"/);
  });

  it("does not publish unagreed operating terms for Experiment 1", () => {
    const needs = read("src/routes/needs.tsx").replace(/\s+/g, " ");
    for (const unagreedTerm of ["15 minutes", "9am", "9pm", "10%"]) {
      assert.ok(!needs.includes(unagreedTerm), `unagreed term surfaced: ${unagreedTerm}`);
    }
    assert.match(needs, /No seller has agreed to participate/);
    assert.match(needs, /No sign-up or live intake is available/);
    assert.match(needs, /fee terms must be agreed/);
  });
});
