import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
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
  processSteps,
  services,
  submitPublicDemandRequest,
  trustPoints,
} from "./content.ts";

const FORBIDDEN_CLAIM_RE =
  /\b(fortune\s*500|testimonial|our clients include|\d+\+|\$\d+\s*(million|billion)|unicorn|award-winning|market leader)\b/i;

function collectCopy(): string[] {
  const blobs: string[] = [
    SITE.name,
    SITE.domain,
    SITE.tagline,
    SITE.description,
  ];
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
      new Response(
        JSON.stringify({ detail: "Legacy demand-understanding is disabled." }),
        { status: 503, headers: { "Content-Type": "application/json" } },
      );
    try {
      assert.deepEqual(
        await submitPublicDemandRequest("TEST-only closed-path fixture", "test-key"),
        { notOpen: true },
      );
    } finally {
      globalThis.fetch = originalFetch;
    }
  });

  it("names Hami without publishing compatibility names as product identities", () => {
    assert.equal(SITE.name, "Hami");
    assert.doesNotMatch(SITE.description, /ForgeOS|Pulse/);
    assert.equal(/service marketplace|trusted service network/i.test(SITE.description), false);
    assert.match(SITE.description, /one evidence-led system/);
    assert.match(SITE.description, /Nepal/);
  });

  it("exposes public-first primary destinations", () => {
    const hrefs = NAV.map((item) => item.to);
    // Broad system surfaces lead; the work board remains a secondary mechanism.
    assert.deepEqual(hrefs, [
      "/",
      "/discoveries",
      "/feed",
      "/opportunities",
      "/actions",
      "/group/businesses",
    ]);
    const publicHrefs = new Set<string>(hrefs);
    for (const path of FORBIDDEN_PUBLIC_PATHS) {
      assert.equal(publicHrefs.has(path), false, `nav leaked ${path}`);
    }
  });

  it("keeps commercial services separate from prototype capabilities", () => {
    assert.equal(services.length, 6);
    assert.ok(getService("software"));
    assert.equal(getService("ocr"), undefined);
    const kinds = new Set(capabilities.map((item) => item.kind));
    assert.ok(kinds.has("commercial"));
    assert.ok(kinds.has("prototype"));
    assert.equal(
      capabilities.filter((item) => item.kind === "prototype").length,
      1,
    );
  });

  it("labels group areas as strategic directions, not subsidiaries", () => {
    assert.ok(groupAreas.length >= 5);
    for (const area of groupAreas) {
      assert.equal(area.status, "strategic direction");
    }
    assert.equal(processSteps.map((step) => step.title).join(" → "), "Understand → Build → Operate → Improve");
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
    assert.doesNotMatch(
      closedCopy,
      /paused until a monitored mailbox is configured|Contact mailbox pending|A monitored contact address has not been configured yet/i,
    );
    const form = readFileSync(join(sourceDir, "../components/pages/project-form.tsx"), "utf8");
    assert.match(form, /No personal details are collected, sent, or stored here/);
  });
});

describe("Hami public root", () => {
  const root = join(dirname(fileURLToPath(import.meta.url)), "../..");

  it("sets baseline security headers without enforcing the report-only CSP", () => {
    const config = JSON.parse(readFileSync(join(root, "vercel.json"), "utf8")) as {
      headers?: Array<{ source?: string; headers?: Array<{ key: string; value: string }> }>;
    };
    const headers =
      config.headers?.find(({ source }) => source === "/(.*)")?.headers ?? [];
    const values = new Map(headers.map(({ key, value }) => [key, value]));
    assert.equal(values.get("X-Content-Type-Options"), "nosniff");
    assert.equal(values.get("Referrer-Policy"), "strict-origin-when-cross-origin");
    assert.equal(values.get("X-Frame-Options"), "DENY");
    assert.equal(
      values.get("Permissions-Policy"),
      "camera=(), microphone=(), geolocation=()",
    );
    assert.match(values.get("Content-Security-Policy-Report-Only") ?? "", /frame-src https:\/\/cal\.com/);
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
    const privacy = readFileSync(join(root, "src/routes/privacy.tsx"), "utf8");
    const vercel = readFileSync(join(root, "vercel.json"), "utf8");
    const ogSite = JSON.parse(readFileSync(join(root, "src/lib/og/site.json"), "utf8")) as {
      title?: string;
    };
    assert.match(home, /createFileRoute\("\/"\)/);
    assert.equal(ogSite.title, "Hami");
    assert.doesNotMatch(home, /Navigate to=/);
    // Home is the person's System, not a post/request board.
    assert.match(home, /A system that keeps observing reality/);
    assert.match(home, /useSystemState/);
    assert.match(home, /<Link to="\/forge-bot-intake">/);
    assert.match(home, /Share a business need/);
    assert.match(home, /For business owners, Hami helps clarify a need and find a practical next step/);
    assert.match(home, /<Welcome onStart={update} state={state}/);
    assert.match(home, /<SystemEditor state={state} onSave={onStart}/);
    assert.match(home, /derivePaths/);
    assert.match(home, /relevantFeed/);
    assert.match(home, /loadPublicFeed/);
    assert.match(home, /Paths are possibilities, not promises/);
    assert.match(home, /Personal context is separate from the public world/);
    assert.match(home, /Guests can keep temporary context in this tab/);
    assert.match(home, /signed-in users can save it privately/);
    assert.match(home, /function CurrentPaths/);
    assert.match(home, /Start with what is actually available/);
    assert.match(home, /to="\/group\/businesses"/);
    assert.doesNotMatch(home, /Browse or post work|to="\/domain"/);
    assert.match(work, /to: "\/domain"/);
    assert.match(header, /Edit my context/);
    assert.match(header, /to="\/system"/);
    const system = readFileSync(join(root, "src/routes/system.tsx"), "utf8");
    assert.match(system, /Back to System overview/);
    assert.match(system, /to="\/"/);
    assert.match(system, /Edit personal context/);
    assert.match(footer, /Edit personal context/);
    assert.match(footer, /For businesses/);
    assert.match(footer, /to: "\/group\/businesses"/);
    assert.doesNotMatch(footer, /Share a need privately/);
    assert.match(header, /label: "For businesses", to: "\/group\/businesses"/);
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
    assert.doesNotMatch(`${header}\n${footer}\n${forgeBot}`, /\/privacy/);
    assert.match(owner, /X-API-Key/);
    assert.doesNotMatch(owner, /localStorage|sessionStorage|dangerouslySetInnerHTML/);
    assert.match(vercel, /X-Robots-Tag/);
    assert.equal(sitemap.includes("/owner"), false);
    assert.equal(sitemap.includes("/privacy"), false);
    assert.doesNotMatch(discoveries, /loadSubstrateDiscoveries|\/api\/forge\/substrate/);
    assert.match(discoveries, /does not request owner-authorized substrate records/);
    assert.match(discoveries, /Opening this page does not run discovery/);
    assert.doesNotMatch(discoveries, /discovery\/runs/);
    assert.match(header, /to: "\/request"/);
    assert.doesNotMatch(header, /Review actions|to="\/operations"|to="\/actions"/);
    assert.doesNotMatch(footer, /Service categories|to="\/services"|to="\/contact"/);
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
    assert.match(sitemap, /https:\/\/forge-os-ebon\.vercel\.app\/providers/);
    assert.match(sitemap, /https:\/\/forge-os-ebon\.vercel\.app\/feed/);
    assert.match(sitemap, /https:\/\/forge-os-ebon\.vercel\.app\/domain/);
    assert.match(sitemap, /https:\/\/forge-os-ebon\.vercel\.app\/discoveries/);
    assert.equal(robots.includes("sanipoperations.com.np"), false);
    assert.match(robots, /Sitemap: https:\/\/forge-os-ebon\.vercel\.app\/sitemap\.xml/);
    assert.match(work, /to: "\/domain"/);
  });
});
