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
    ]);
    for (const path of FORBIDDEN_PUBLIC_PATHS) {
      assert.equal(hrefs.includes(path as any), false, `nav leaked ${path}`);
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
    const footer = readFileSync(join(dirname(fileURLToPath(import.meta.url)), "../components/layout/site-footer.tsx"), "utf8");
    const form = readFileSync(join(dirname(fileURLToPath(import.meta.url)), "../components/pages/project-form.tsx"), "utf8");
    assert.match(footer, /Contact mailbox pending/);
    assert.match(form, /No personal details are collected, sent, or stored here/);
  });
});

describe("Hami public root", () => {
  const root = join(dirname(fileURLToPath(import.meta.url)), "../..");

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
    assert.match(home, /createFileRoute\("\/"\)/);
    assert.doesNotMatch(home, /Navigate to=/);
    // Home is the person's System, not a post/request board.
    assert.match(home, /A system that keeps observing reality/);
    assert.match(home, /useSystemState/);
    assert.match(home, /derivePaths/);
    assert.match(home, /relevantFeed/);
    assert.match(home, /loadPublicFeed/);
    assert.match(home, /Paths are possibilities, not promises/);
    assert.match(home, /Your context stays on this device; nothing is posted or shared/);
    assert.doesNotMatch(home, /Browse or post work|to="\/domain"/);
    assert.match(work, /to: "\/domain"/);
    assert.match(header, /My System/);
    assert.match(header, /to="\/system"/);
    assert.match(discoveries, /loadSubstrateDiscoveries/);
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
