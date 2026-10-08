import assert from "node:assert/strict";
import { existsSync, readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { describe, it } from "node:test";
import { fileURLToPath } from "node:url";
import {
  NAV,
  SITE,
  capabilities,
  currentOffers,
  FORBIDDEN_PUBLIC_PATHS,
  getService,
  groupAreas,
  getPublicDemandRequestEnabled,
  processSteps,
  services,
  submitPublicDemandRequest,
  trustPoints,
} from "./content.ts";
import { candidateNeeds, needsCount, needsRounds } from "./needs.ts";

const FORBIDDEN_CLAIM_RE =
  /\b(fortune\s*500|testimonial|our clients include|\d+\+|\$\d+\s*(million|billion)|unicorn|award-winning|market leader)\b/i;

function collectCopy(): string[] {
  const blobs: string[] = [SITE.name, SITE.domain, SITE.tagline, SITE.description];
  for (const item of NAV) blobs.push(item.label, item.to);
  for (const service of services) {
    blobs.push(
      service.title,
      service.short,
      service.body,
      service.problem,
      service.does,
      service.deliverable,
      service.process,
      service.forWho,
      service.next,
    );
  }
  for (const step of processSteps) blobs.push(step.title, step.body);
  for (const cap of capabilities) blobs.push(cap.name, cap.kind, cap.note);
  for (const area of groupAreas) blobs.push(area.name, area.status, area.description);
  for (const offer of currentOffers) {
    blobs.push(offer.title, offer.problem, offer.does, offer.value, offer.start);
  }
  for (const point of trustPoints) blobs.push(point.title, point.body);
  return blobs;
}

describe("Hami public content", () => {
  it("handles the closed legacy demand path without exposing its API error", async () => {
    const originalFetch = globalThis.fetch;
    globalThis.fetch = async () =>
      new Response(JSON.stringify({ detail: "Legacy demand-understanding is disabled." }), {
        status: 503,
        headers: { "Content-Type": "application/json" },
      });
    try {
      assert.deepEqual(
        await submitPublicDemandRequest("TEST-only closed-path fixture", "test-key"),
        { notOpen: true },
      );
    } finally {
      globalThis.fetch = originalFetch;
    }
  });

  it("reads the existing public demand gate and fails closed when unavailable", async () => {
    const originalFetch = globalThis.fetch;
    try {
      globalThis.fetch = async (input) => {
        assert.equal(input, "/api/signals/public-request/config");
        return new Response(JSON.stringify({ enabled: false }), {
          headers: { "Content-Type": "application/json" },
        });
      };
      assert.equal(await getPublicDemandRequestEnabled(), false);

      globalThis.fetch = async () =>
        new Response(JSON.stringify({ enabled: true }), {
          headers: { "Content-Type": "application/json" },
        });
      assert.equal(await getPublicDemandRequestEnabled(), true);

      globalThis.fetch = async () => {
        throw new Error("TEST-only unavailable request");
      };
      assert.equal(await getPublicDemandRequestEnabled(), null);
    } finally {
      globalThis.fetch = originalFetch;
    }
  });

  it("names Hami without publishing compatibility names as product identities", () => {
    assert.equal(SITE.name, "Hami");
    assert.doesNotMatch(SITE.description, /ForgeOS|Pulse/);
    assert.equal(/service marketplace|trusted service network/i.test(SITE.description), false);
    assert.match(SITE.description, /being built in Kathmandu/);
    assert.match(SITE.description, /Pre-revenue/);
  });

  it("exposes public-first primary destinations", () => {
    const root = join(dirname(fileURLToPath(import.meta.url)), "../..");
    const hrefs = NAV.map((item) => item.to);
    // The primary navigation keeps global records, not a specific experiment.
    // Join Hami is a separate header button, not a nav menu item.
    assert.deepEqual(hrefs, ["/", "/discoveries", "/unknowns", "/about"]);
    const publicHrefs = new Set<string>(hrefs);
    for (const path of FORBIDDEN_PUBLIC_PATHS) {
      assert.equal(publicHrefs.has(path), false, `nav leaked ${path}`);
    }
    // Join Hami IS in the header as a CTA button for signed-out visitors.
    // Join leads to signup mode, Login is a separate link to sign-in mode.
    // TanStack Router uses structured search params, not query strings.
    const header = readFileSync(join(root, "src/components/layout/site-header.tsx"), "utf8");
    assert.match(header, /Join Hami/);
    assert.match(header, /to="\/login"/);
    assert.match(header, /search=\{\{\s*mode:\s*"sign-up"\s*\}\}/);
    assert.match(header, /Login/);
    assert.match(header, /search=\{\{\s*mode:\s*"sign-in"\s*\}\}/);
    const footer = readFileSync(join(root, "src/components/layout/site-footer.tsx"), "utf8");
    assert.doesNotMatch(footer, /Sign in \/ Sign up/);
  });

  it("keeps commercial services separate from prototype capabilities", () => {
    assert.equal(services.length, 6);
    assert.ok(getService("software"));
    assert.equal(getService("ocr"), undefined);
    const kinds = new Set(capabilities.map((item) => item.kind));
    assert.ok(kinds.has("commercial"));
    assert.ok(kinds.has("prototype"));
    assert.equal(capabilities.filter((item) => item.kind === "prototype").length, 1);
  });

  it("labels group areas as strategic directions, not subsidiaries", () => {
    assert.ok(groupAreas.length >= 5);
    for (const area of groupAreas) {
      assert.equal(area.status, "strategic direction");
    }
    assert.equal(
      processSteps.map((step) => step.title).join(" → "),
      "Understand → Build → Operate → Improve",
    );
  });

  it("does not ship fake metrics, testimonials, or phantom clients", () => {
    for (const blob of collectCopy()) {
      assert.equal(FORBIDDEN_CLAIM_RE.test(blob), false, blob);
      assert.equal(/\b\/tools\b/.test(blob), false, blob);
    }
  });

  it("does not present placeholder contact details as live destinations", () => {
    assert.equal(SITE.email, "");
    assert.equal(SITE.url, "");
    const sourceDir = dirname(fileURLToPath(import.meta.url));
    const closedCopy = [
      "../components/layout/site-footer.tsx",
      "../components/pages/project-form.tsx",
      "../components/pages/project-inquiry-cta.tsx",
      "../routes/contact.tsx",
      "../routes/forge-bot-intake.tsx",
    ]
      .map((path) => readFileSync(join(sourceDir, path), "utf8"))
      .join("\n");
    assert.match(closedCopy, /Online inquiries are not open yet/);
    const staleContactCopy = [
      "Contact mailbox pending",
      "paused until a monitored mailbox is configured",
      "paused until Hami has a monitored mailbox",
      "A monitored contact address has not been configured yet",
    ];
    for (const staleCopy of staleContactCopy) {
      assert.equal(
        closedCopy.toLowerCase().includes(staleCopy.toLowerCase()),
        false,
        `obsolete contact copy remains: ${staleCopy}`,
      );
    }
    const form = readFileSync(join(sourceDir, "../components/pages/project-form.tsx"), "utf8");
    assert.match(form, /No personal details are collected, sent, or stored here/);
  });
});

describe("Hami candidate needs", () => {
  it("publishes grounded, honestly-labeled needs and nothing else", () => {
    assert.equal(candidateNeeds.length, needsCount);
    assert.ok(needsCount >= 10, "the needs surface must carry real findings");
    assert.ok(needsRounds >= 1);
    const ids = new Set<string>();
    for (const need of candidateNeeds) {
      assert.ok(need.id && !ids.has(need.id), `duplicate or empty id: ${need.id}`);
      ids.add(need.id);
      assert.ok(need.title.length > 0);
      assert.ok(need.segment.length > 0);
      assert.ok(["known", "unknown", "partially"].includes(need.knownToThem));
      assert.ok(need.need.length > 20, `${need.id}: need statement too thin`);
      assert.ok(need.observed.length > 60, `${need.id}: observed evidence too thin`);
      assert.ok(need.sources.length >= 1, `${need.id}: no sources`);
      assert.ok(need.round.length > 0);
      assert.ok(need.question.length > 10, `${need.id}: no sharp question`);
      assert.ok(
        ["high", "medium", "low"].includes(need.confidence),
        `${need.id}: no confidence grade`,
      );
      assert.ok(need.weakestLink.length > 20, `${need.id}: no weakest link`);
      // No manufactured voices: needs describe observations, never quote people.
      assert.doesNotMatch(need.observed, /“[^”]{80,}”/, `${need.id}: long quote looks invented`);
    }
  });

  it("keeps the needs route honest: wedge, service offer, empty week log", () => {
    const sourceDir = dirname(fileURLToPath(import.meta.url));
    const route = readFileSync(join(sourceDir, "../routes/needs.tsx"), "utf8");
    // The internal backlog is gone from the public surface.
    assert.doesNotMatch(route, /candidateNeeds/);
    assert.doesNotMatch(route, /@\/lib\/needs/);
    // Hami is not a gadget: no tool/calculator framing on this page.
    assert.doesNotMatch(route, /\/prototype\/inbox/);
    assert.doesNotMatch(route, /inbox tool/i);
    // The page states the honest position and the empty week log.
    assert.match(route, /pre-revenue/i);
    assert.match(route, /no merchants served yet/i);
    assert.match(route, /No week has run yet/);
    assert.match(route, /will not be filled with\s*\n?\s*projections/);
    // The offer is a service being tested, explicitly a hypothesis.
    assert.match(route, /not a tool the seller operates/i);
    assert.match(route, /hypothesis, not an established offer/i);
    assert.match(route, /createFileRoute\("\/needs"\)/);
  });
});

describe("Hami prototype honesty", () => {
  it("labels the inbox prototype as a prototype with no fake data", () => {
    const sourceDir = dirname(fileURLToPath(import.meta.url));
    const route = readFileSync(join(sourceDir, "../routes/prototype.inbox.tsx"), "utf8");
    assert.match(route, /Prototype/);
    assert.match(route, /not a live product/i);
    assert.match(route, /No inquiries yet/);
    assert.match(route, /honest empty state/);
    assert.match(route, /createFileRoute\("\/prototype\/inbox"\)/);
    // The prototype is historical material, not public identity.
    // Per HAMI CONTINUITY LAW: it must not appear in footer or nav.
    const footer = readFileSync(join(sourceDir, "../components/layout/site-footer.tsx"), "utf8");
    assert.doesNotMatch(footer, /Inbox prototype/);
    assert.doesNotMatch(footer, /\/prototype\/inbox/);
    const root = join(sourceDir, "../..");
    const sitemap = readFileSync(join(root, "public/sitemap.xml"), "utf8");
    assert.equal(sitemap.includes("/prototype/inbox"), false);
  });
});

describe("Hami forge console", () => {
  it("lives only behind the owner key — no public route", () => {
    const sourceDir = dirname(fileURLToPath(import.meta.url));
    // No public /forge route exists.
    assert.equal(existsSync(join(sourceDir, "../routes/forge.tsx")), false);
    const owner = readFileSync(join(sourceDir, "../routes/owner.tsx"), "utf8");
    const widget = readFileSync(join(sourceDir, "../components/forge/forge-console.tsx"), "utf8");
    // The widgets exercise the real engine, not a mock.
    assert.match(widget, /verifyRound/);
    assert.match(widget, /ripenessQueue/);
    assert.match(widget, /isAngleTried/);
    assert.match(widget, /@\/lib\/forge\/assistant/);
    // Rendered only after unlock: the import lives at the top, but the
    // widget JSX appears only in the unlocked branch.
    const marker = "{!consoleState || !readiness ? (";
    assert.ok(owner.includes(marker));
    const [locked, unlocked] = owner.split(marker);
    assert.equal(locked.includes("<ForgeConsoleWidgets />"), false);
    assert.equal(unlocked.includes("<ForgeConsoleWidgets />"), true);
    // The owner page stays unindexed and unlinked from the nav.
    assert.match(owner, /noindex/);
    assert.equal(
      NAV.some((item) => (item.to as string) === "/owner"),
      false,
    );
  });
});

describe("Hami public root", () => {
  const root = join(dirname(fileURLToPath(import.meta.url)), "../..");

  it("sets baseline security headers without enforcing the report-only CSP", () => {
    const config = JSON.parse(readFileSync(join(root, "vercel.json"), "utf8")) as {
      headers?: Array<{ source?: string; headers?: Array<{ key: string; value: string }> }>;
    };
    const headers = config.headers?.find(({ source }) => source === "/(.*)")?.headers ?? [];
    const values = new Map(headers.map(({ key, value }) => [key, value]));
    assert.equal(values.get("X-Content-Type-Options"), "nosniff");
    assert.equal(values.get("Referrer-Policy"), "strict-origin-when-cross-origin");
    assert.equal(values.get("X-Frame-Options"), "DENY");
    assert.equal(values.get("Permissions-Policy"), "camera=(), microphone=(), geolocation=()");
    assert.match(
      values.get("Content-Security-Policy-Report-Only") ?? "",
      /frame-src https:\/\/cal\.com/,
    );
    assert.equal(values.has("Content-Security-Policy"), false);
  });

  it("serves a real Hami home distinct from Network and does not publish the Sanip site", () => {
    const home = readFileSync(join(root, "src/routes/index.tsx"), "utf8");
    const network = readFileSync(join(root, "src/routes/feed.tsx"), "utf8");
    const opportunities = readFileSync(join(root, "src/routes/opportunities.tsx"), "utf8");
    const actions = readFileSync(join(root, "src/routes/actions.tsx"), "utf8");
    const sitemap = readFileSync(join(root, "public/sitemap.xml"), "utf8");
    const robots = readFileSync(join(root, "public/robots.txt"), "utf8");
    const work = readFileSync(join(root, "src/routes/work.tsx"), "utf8");
    const discoveries = readFileSync(join(root, "src/routes/discoveries.tsx"), "utf8");
    const header = readFileSync(join(root, "src/components/layout/site-header.tsx"), "utf8");
    const footer = readFileSync(join(root, "src/components/layout/site-footer.tsx"), "utf8");
    const businesses = readFileSync(join(root, "src/routes/group.businesses.tsx"), "utf8");
    const forgeBot = readFileSync(join(root, "src/routes/forge-bot-intake.tsx"), "utf8");
    const owner = readFileSync(join(root, "src/routes/owner.tsx"), "utf8");
    const demandForm = readFileSync(
      join(root, "src/components/pages/demand-intake-form.tsx"),
      "utf8",
    );
    const request = readFileSync(join(root, "src/routes/request.tsx"), "utf8");
    const privacy = readFileSync(join(root, "src/routes/privacy.tsx"), "utf8");
    const vercel = readFileSync(join(root, "vercel.json"), "utf8");
    const ogSite = JSON.parse(readFileSync(join(root, "src/lib/og/site.json"), "utf8")) as {
      title?: string;
    };
    assert.match(home, /createFileRoute\("\/"\)/);
    assert.equal(ogSite.title, "Hami");
    assert.doesNotMatch(home, /Navigate to=/);
    // Home per the unknowns-surface design: hero, primitives, unknown counts, climb, findings.
    assert.match(home, /Discover what matters/);
    assert.match(home, /Act on it/);
    assert.match(home, /Hami is a living system that understands what people need/);
    assert.match(home, /Built in Kathmandu/);
    assert.match(home, /Serving everywhere equally/);
    assert.match(home, /RealityLoop/);
    // Per IA: homepage = previews only, no own content
    assert.doesNotMatch(home, /The power of the unknown/);
    assert.doesNotMatch(home, /Very big, very small/);
    assert.doesNotMatch(home, /What we have learned/);
    // Previews use same components/API as pages
    assert.match(home, /FindingsPreview/);
    assert.match(home, /UnknownsPreview/);
    assert.match(home, /ExperimentsPreview/);
    assert.match(home, /loadDiscoveries/);
    assert.match(home, /loadPublicUnknowns/);
    assert.match(home, /See all findings/);
    assert.match(home, /See all unknowns/);
    assert.match(home, /See all experiments/);
    assert.doesNotMatch(home, /to="\/prototype\/inbox"|Try the free inbox tool/);
    assert.match(
      home,
      /<Hero \/>[\s\S]*<FindingsPreview \/>[\s\S]*<UnknownsPreview \/>[\s\S]*<ExperimentsPreview \/>[\s\S]*<AboutLink \/>[\s\S]*<HomeFooter \/>/,
    );
    assert.match(home, /Honest status/i);
    assert.match(home, /pre-revenue/i);
    assert.match(home.replace(/\s+/g, " "), /no participants or results to report/);
    // The wedge is never the headline.
    const h1 = home.replace(/\s+/g, " ").match(/<h1[^>]*>(.*?)<\/h1>/)?.[1] ?? "";
    assert.match(h1, /Discover what matters/);
    assert.doesNotMatch(h1, /slow reply|inbox|seller|business|customer support|sale/i);
    const primarySystem = home.slice(0, home.indexOf("function FindingsPreview"));
    assert.doesNotMatch(
      primarySystem,
      /inbox|customer support|lead[- ]generation|for online sellers|for businesses|commerce platform|seller reply service/i,
    );
    // No grand unproven claims, no toy form, no keyword-salad feed.
    assert.doesNotMatch(home, /Finds what people need/);
    assert.doesNotMatch(home, /Share a business need/);
    assert.doesNotMatch(home, /SystemEditor/);
    assert.doesNotMatch(home, /loadPublicFeed/);
    assert.doesNotMatch(home, /useSystemState/);
    assert.doesNotMatch(home, /WorldStream/);
    // The homepage maps existing public views without implying they have all run.
    assert.doesNotMatch(home, /function CurrentPaths/);
    assert.doesNotMatch(home, /to="\/group\/businesses"/);
    assert.match(home, /to="\/discoveries"/);
    // The homepage maps existing public views without implying they have all run:
    // each preview links to its page and carries an honest empty state.
    for (const empty of [
      "No findings with recorded consequences yet.",
      "No unknowns recorded yet.",
      "No experiments yet.",
    ]) {
      assert.ok(home.includes(empty), `homepage missing honest empty state: ${empty}`);
    }
    for (const label of ["See all findings", "See all unknowns", "See all experiments"]) {
      assert.ok(home.includes(label), `homepage missing preview link: ${label}`);
    }
    assert.doesNotMatch(home, /to="\/operations"/);
    // Header: no context form, no closed-intake links, no Sign in.
    assert.doesNotMatch(header, /Sign in/);
    assert.doesNotMatch(header, /Edit my context/);
    assert.doesNotMatch(header, /to="\/system"/);
    assert.doesNotMatch(header, /Share a need/);
    const system = readFileSync(join(root, "src/routes/system.tsx"), "utf8");
    assert.match(system, /Back to home/);
    assert.match(system, /to="\/"/);
    // Footer: new link groups, old ones unlinked.
    assert.doesNotMatch(footer, /Edit personal context/);
    assert.doesNotMatch(footer, /Share a need/);
    assert.doesNotMatch(footer, /Work board/);
    assert.match(footer, /Built in Kathmandu/);
    assert.ok(NAV.some((item) => item.label === "Home" && item.to === "/"));
    assert.ok(NAV.some((item) => item.label === "About" && item.to === "/about"));
    assert.ok(NAV.some((item) => item.label === "Findings" && item.to === "/discoveries"));
    assert.ok(NAV.some((item) => item.label === "Unknowns" && item.to === "/unknowns"));
    assert.doesNotMatch(header, /Experiments|\/experiments/);
    assert.doesNotMatch(header, /Inbox tool|\/prototype\/inbox/);
    // Per HAMI CONTINUITY LAW: inbox is historical material, not public identity.
    assert.doesNotMatch(footer, /Inbox prototype/);
    assert.doesNotMatch(footer, /\/prototype\/inbox/);
    assert.doesNotMatch(footer, /Experiment 1 \(not started\)/);
    assert.ok(
      !NAV.some((item) => (item.label as string) === "Contact"),
      "Contact is in the nav without a real contact route",
    );
    assert.match(header, /aria-current={active \? "page" : undefined}/);
    assert.match(businesses, /to="\/forge-bot-intake"/);
    assert.match(businesses, /online intake is closed/i);
    assert.match(forgeBot, /name: "robots", content: "noindex,nofollow"/);
    assert.match(forgeBot, /Online inquiries are not open yet/);
    assert.match(forgeBot, /Booking link available/);
    assert.match(forgeBot, /Status: <strong>REQUESTED<\/strong>/);
    assert.match(forgeBot, /permanently opt out and erase/);
    assert.doesNotMatch(forgeBot, /contact_email|haminp\.forge@gmail\.com/i);
    assert.match(owner, /createFileRoute\("\/owner"\)/);
    assert.match(owner, /name: "robots", content: "noindex, nofollow, noarchive"/);
    assert.match(privacy, /createFileRoute\("\/privacy"\)/);
    assert.match(privacy, /name: "robots", content: "noindex, nofollow"/);
    assert.match(privacy, /automatically\s+erased 30 days/);
    assert.match(privacy, /Vercel hosts the website, Neon provides the database/);
    // No public signup: terms and privacy are reachable from the footer,
    // but /login is deliberately unlinked (owner login only).
    assert.match(footer, /\/terms/);
    assert.match(footer, /\/privacy/);
    assert.doesNotMatch(footer, /\/login/);
    assert.doesNotMatch(`${header}\n${forgeBot}`, /\/privacy/);
    assert.match(owner, /X-API-Key/);
    assert.doesNotMatch(owner, /localStorage|sessionStorage|dangerouslySetInnerHTML/);
    assert.match(owner, /publicly reachable but not linked from the\s+public site/i);
    assert.match(owner, /the API protects owner data and actions/i);
    assert.match(demandForm, /availability !== "open"/);
    assert.match(demandForm, /Online inquiries are not open yet/);
    assert.match(demandForm, /This page does not collect or submit a note/);
    assert.match(demandForm, /getPublicDemandRequestEnabled/);
    assert.match(request, /<DemandIntakeForm \/>/);
    assert.match(vercel, /X-Robots-Tag/);
    assert.equal(sitemap.includes("/owner"), false);
    assert.equal(sitemap.includes("/privacy"), false);
    assert.doesNotMatch(discoveries, /loadSubstrateDiscoveries|\/api\/forge\/substrate/);
    assert.match(discoveries, /does not request owner-authorized substrate records/);
    assert.match(discoveries, /Opening this page does not run discovery/);
    assert.doesNotMatch(discoveries, /discovery\/runs/);
    // The closed-intake link is gone from the header entirely.
    assert.doesNotMatch(header, /to: "\/request"/);
    assert.doesNotMatch(header, /Review actions|to="\/operations"|to="\/actions"/);
    assert.doesNotMatch(footer, /Service categories|to="\/services"/);
    assert.doesNotMatch(footer, /Explore the network/);
    assert.doesNotMatch(footer, /"\/feed"/);
    assert.doesNotMatch(footer, /Online inquiries are not open yet/);
    const domain = readFileSync(join(root, "src/routes/domain.tsx"), "utf8");
    assert.match(domain, /This post will be public/);
    assert.match(domain, /Do not include phone numbers, email/);
    assert.match(network, /createFileRoute\("\/feed"\)/);
    assert.match(network, /Hami Network/);
    assert.match(opportunities, /createFileRoute\("\/opportunities"\)/);
    assert.match(actions, /createFileRoute\("\/actions"\)/);
    assert.doesNotMatch(actions, /to="\/operations"|Open the approval queue/);
    assert.equal(home.includes("Sanip Ops"), false);
    assert.equal(home.includes("parent operations and infrastructure group"), false);
    assert.equal(sitemap.includes("sanipoperations.com.np"), false);
    assert.equal(sitemap.includes("Sanip"), false);
    assert.match(sitemap, /https:\/\/haminp.vercel.app\/providers/);
    assert.match(sitemap, /https:\/\/haminp.vercel.app\/feed/);
    assert.match(sitemap, /https:\/\/haminp.vercel.app\/domain/);
    assert.match(sitemap, /https:\/\/haminp.vercel.app\/discoveries/);
    assert.equal(robots.includes("sanipoperations.com.np"), false);
    assert.match(robots, /Sitemap: https:\/\/haminp.vercel.app\/sitemap\.xml/);
    assert.match(work, /to: "\/domain"/);
  });
});
