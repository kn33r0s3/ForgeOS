import assert from "node:assert/strict";
import { describe, it } from "node:test";
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
    SITE.legalName,
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

describe("Forge public content", () => {
  it("names the network without locking it to one purpose", () => {
    assert.equal(SITE.name, "Forge");
    assert.equal(SITE.legalName, "Forge");
    assert.equal(/service marketplace|trusted service network/i.test(SITE.description), false);
    assert.match(SITE.description, /Nepal/);
    assert.match(SITE.description, /services/i);
  });

  it("exposes the public paths and never routes tools", () => {
    const hrefs = NAV.map((item) => item.to);
    assert.deepEqual(hrefs, [
      "/",
      "/services",
      "/providers",
      "/domain",
      "/discoveries",
      "/about",
      "/contact",
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
});
