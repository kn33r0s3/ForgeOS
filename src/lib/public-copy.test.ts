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
  const home = () => read("src/routes/index.tsx");
  const header = () => read("src/components/layout/site-header.tsx");
  const footer = () => read("src/components/layout/site-footer.tsx");

  it("has one plain headline and the missed-inquiry offer, in English and Nepali", () => {
    const src = home();
    assert.match(src, /Never miss a sale to a slow reply/);
    assert.match(src, /ढिलो जवाफले बिक्री नगुमाउनुहोस्/);
    assert.match(src, /you pay only for the sales that come back/i);
  });

  it("carries one honest status line and one real CTA", () => {
    const src = home();
    assert.match(src, /Honest status/i);
    assert.match(src, /no customers yet/i);
    assert.match(src, /One seller, one week/i);
    assert.match(src, /\/prototype\/inbox/);
    assert.match(src, /No signup/i);
  });

  it("never shows the removed placeholders again", () => {
    const blob = home() + header() + footer();
    const banned = [
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
      "verification pending",
    ];
    for (const phrase of banned) {
      assert.ok(
        !blob.toLowerCase().includes(phrase.toLowerCase()),
        `banned placeholder reappeared: ${phrase}`,
      );
    }
  });

  it("homepage titles never carry Forge", () => {
    const src = home();
    assert.ok(!/title[^"']*["'][^>]*Forge/i.test(src), "Forge in a homepage title");
    assert.ok(!/og:title/i.test(src) || /content:\s*"Hami"/.test(src), "og:title must say Hami");
  });

  it("main nav is exactly Hami, Inbox tool, What we've learned, Contact", () => {
    const src = read("src/lib/content.ts");
    assert.match(src, /\{\s*label:\s*"Hami",\s*to:\s*"\/"/);
    assert.match(src, /\{\s*label:\s*"Inbox tool",\s*to:\s*"\/prototype\/inbox"/);
    assert.match(src, /\{\s*label:\s*"What we've learned",\s*to:\s*"\/what-we-learned"/);
    assert.match(src, /\{\s*label:\s*"Contact",\s*to:\s*"\/contact"/);
    const navBlock = src.slice(src.indexOf("export const NAV"), src.indexOf("] as const;"));
    for (const old of ["Discoveries", "World", "Hypotheses", "Actions", "For businesses"]) {
      assert.ok(!navBlock.includes(`"${old}"`), `old nav item reappeared: ${old}`);
    }
  });

  it("what-we-learned renders engine data through the API module, nothing hand-written", () => {
    const src = read("src/routes/what-we-learned.tsx");
    assert.ok(
      src.includes("@/lib/unknowns-api"),
      "what-we-learned must import the engine API module",
    );
    assert.match(src, /fetchUnknowns/);
    // Honest states: failure and empty are shown, not filled in.
    assert.match(src, /unavailable right now/i);
    assert.match(src, /Nothing recorded yet/);
    assert.match(src, /will not invent findings/i);
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
});
