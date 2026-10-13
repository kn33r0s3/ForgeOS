/**
 * Feature registry guard: every LIVE feature in features.json must be
 * present at its route/endpoint. Removing or renaming a live feature
 * without updating the registry fails this test.
 */
import { describe, it } from "node:test";
import assert from "node:assert/strict";
import { existsSync, readFileSync, readdirSync } from "node:fs";
import { fileURLToPath } from "node:url";
import path from "node:path";
import { FOOTER_GROUPS, NAV, PUBLIC_SYSTEM_PATHS, SYSTEM_PATHWAYS } from "./hami-system.ts";
import { groupAreas } from "./content.ts";

const root = path.dirname(path.dirname(fileURLToPath(import.meta.url)));
const registry = JSON.parse(
  readFileSync(path.join(root, "..", "features.json"), "utf8"),
);

function routeFile(route: string): string {
  // "/" -> index.tsx, "/prototype/inbox" -> prototype.inbox.tsx
  const name = route === "/" ? "index" : route.slice(1).replace(/\//g, ".");
  return path.join(root, "routes", `${name}.tsx`);
}

describe("feature registry", () => {
  it("every live page feature has its route file", () => {
    const missing: string[] = [];
    for (const f of registry.features) {
      if (f.status !== "live" || !f.route || f.route.startsWith("/api")) continue;
      if (!existsSync(routeFile(f.route))) missing.push(`${f.id} -> ${f.route}`);
    }
    assert.deepEqual(missing, [], `live features missing route files: ${missing.join(", ")}`);
  });

  it("every live API feature has its endpoint registered in the backend", () => {
    const backend = readFileSync(
      path.join(root, "..", "backend", "app", "main.py"),
      "utf8",
    );
    const apiIndex = readFileSync(
      path.join(root, "..", "backend", "app", "api", "__init__.py"),
      "utf8",
    );
    // Public router prefixes live in their own modules.
    let haystack = backend + apiIndex;
    for (const f of registry.features) {
      if (f.status !== "live" || !f.endpoint || !f.endpoint.includes("/public")) continue;
      haystack += readFileSync(
        path.join(root, "..", "backend", "app", "api", "public.py"),
        "utf8",
      );
      break;
    }
    const missing: string[] = [];
    for (const f of registry.features) {
      if (f.status !== "live" || !f.endpoint) continue;
      // endpoint like "GET /api/health" -> Vercel routes /api/* to FastAPI,
      // so check the path after the /api prefix is registered.
      const endpointPath =
        f.endpoint.split(" ").pop().replace(/^\/api/, "").replace(/\/\*$/, "") || "/";
      if (!haystack.includes(`"${endpointPath}"`) && !haystack.includes(`'${endpointPath}'`)) {
        missing.push(`${f.id} -> ${f.endpoint}`);
      }
    }
    assert.deepEqual(missing, [], `live APIs missing endpoints: ${missing.join(", ")}`);
  });

  it("every implemented top-level page route has an explicit registry lifecycle state", () => {
    const routeFiles = readdirSync(path.join(root, "routes")).filter((name) => name.endsWith(".tsx"));
    const routes = new Set<string>();
    for (const filename of routeFiles) {
      const base = filename.slice(0, -4);
      if (base === "__root" || base === "$") continue;
      const normalized = base.endsWith(".index") ? base.slice(0, -".index".length) : base;
      routes.add(base === "index" ? "/" : "/" + normalized.replace(/\./g, "/"));
    }
    const registered = new Set(registry.features.map((feature: { route: string }) => feature.route));
    const missing = [...routes].filter((route) => !registered.has(route));
    assert.deepEqual(missing, [], `route files missing a registry entry: ${missing.join(", ")}`);
  });

  it("all Hami navigation and pathway routes are registered as live", () => {
    const required = [
      ...NAV.map((item) => item.to),
      ...FOOTER_GROUPS.flatMap((group) => group.items.map((item) => item.to)),
      ...PUBLIC_SYSTEM_PATHS,
    ];
    const missing = [...new Set(required)].filter((route) =>
      !registry.features.some((feature: { route: string; status: string }) => feature.route === route && feature.status === "live"),
    );
    assert.deepEqual(missing, [], `public Hami pathways missing a live registry entry: ${missing.join(", ")}`);
  });

  it("shared CTA destinations match the context that renders them", () => {
    const component = readFileSync(path.join(root, "..", "src/components/layout/cta-band.tsx"), "utf8");
    assert.ok(component.includes('to = "/providers"'));
    assert.ok(component.includes('actionLabel = "Browse verified providers"'));
    assert.ok(component.includes("Hami's service catalogue describes Hami's own technical scope"));

    const expected: Array<[string, string, string]> = [
      ["routes/process.tsx", 'to="/services"', 'actionLabel="Explore Hami services"'],
      ["routes/group.businesses.tsx", 'to="/services"', 'actionLabel="Explore Hami services"'],
      ["routes/group.index.tsx", 'to="/process"', 'actionLabel="See how Hami works"'],
      ["components/pages/area-view.tsx", 'to="/group/businesses"', 'actionLabel="See current Hami work"'],
    ];
    for (const [relativePath, target, label] of expected) {
      const source = readFileSync(path.join(root, "..", "src", relativePath), "utf8");
      assert.ok(source.includes(target), `${relativePath} needs destination ${target}`);
      assert.ok(source.includes(label), `${relativePath} needs context-specific CTA label ${label}`);
    }
    for (const pathName of ["/providers", "/services", "/process", "/group/businesses"]) {
      assert.ok(
        registry.features.some((feature: { route: string; status: string }) => feature.route === pathName && feature.status === "live"),
        `shared CTA target ${pathName} must remain a live Hami route`,
      );
    }
  });

  it("every group direction links through the shared component to a live canonical route", () => {
    const broken = groupAreas.filter((area) =>
      !area.href ||
      !area.hrefLabel.trim() ||
      !registry.features.some((feature: { route: string; status: string }) =>
        feature.route === area.href && feature.status === "live",
      ),
    );
    assert.deepEqual(
      broken.map((area) => area.name),
      [],
      "each strategic direction must lead into an existing live Hami surface",
    );
    for (const file of ["routes/group.index.tsx", "routes/group.businesses.tsx"]) {
      const source = readFileSync(path.join(root, file), "utf8");
      assert.ok(source.includes("GroupAreaGrid"), `${file} must reuse the canonical area grid`);
      assert.ok(!source.includes("groupAreas.map"), `${file} must not define another area-card implementation`);
    }
  });

  it("every related Hami pathway points to a live registered route", () => {
    const targets = Object.values(SYSTEM_PATHWAYS).flatMap((links) => links.map((link) => link.to));
    const broken = [...new Set(targets)].filter(
      (route) => !registry.features.some((feature: { route: string; status: string }) => feature.route === route && feature.status === "live"),
    );
    assert.deepEqual(broken, [], `pathways pointing to missing or non-live registry routes: ${broken.join(", ")}`);
  });

  it("every page pathway uses a key in the canonical pathway map", () => {
    const routeDir = path.join(root, "routes");
    const keys = new Set(Object.keys(SYSTEM_PATHWAYS));
    const invalid: string[] = [];
    for (const filename of readdirSync(routeDir).filter((name) => name.endsWith(".tsx"))) {
      const source = readFileSync(path.join(routeDir, filename), "utf8");
      for (const match of source.matchAll(/HamiPathways current="([^"]+)"/g)) {
        if (!keys.has(match[1] as keyof typeof SYSTEM_PATHWAYS)) {
          invalid.push(`${filename}: ${match[1]}`);
        }
      }
    }
    assert.deepEqual(invalid, [], `pages use undefined Hami pathway keys: ${invalid.join(", ")}`);
  });

  it("every live page has a deliberate entry path or is an explicit workflow-only route", () => {
    const sitemap = readFileSync(path.join(root, "..", "public", "sitemap.xml"), "utf8");
    const sitemapPaths = [...sitemap.matchAll(/<loc>https:\/\/haminp\.vercel\.app([^<]*)<\/loc>/g)]
      .map((match) => match[1] || "/");
    const entryPaths = new Set<string>([
      ...NAV.map((item) => item.to),
      ...FOOTER_GROUPS.flatMap((group) => group.items.map((item) => item.to)),
      ...PUBLIC_SYSTEM_PATHS,
      ...Object.values(SYSTEM_PATHWAYS).flatMap((links) => links.map((item) => item.to)),
      ...sitemapPaths,
    ]);
    const routeMatches = (pattern: string, candidate: string) => {
      const expected = pattern.split("/");
      const actual = candidate.split("/");
      return expected.length === actual.length && expected.every((segment, index) =>
        segment.startsWith("$") ? actual[index].length > 0 && !actual[index].startsWith("$") : segment === actual[index],
      );
    };
    // Request status is only addressable after the provider-request flow creates a record.
    const workflowOnly = new Set(["/requests/$id"]);
    const publicPages = registry.features.filter((feature: { route: string; status: string }) =>
      feature.status === "live" && feature.route && !feature.route.startsWith("/api/"),
    );
    const orphaned = publicPages.filter((feature: { route: string }) =>
      !workflowOnly.has(feature.route) &&
      ![...entryPaths].some((candidate) => routeMatches(feature.route, candidate)),
    );
    assert.deepEqual(
      orphaned.map((feature: { route: string; name: string }) => `${feature.name} (${feature.route})`),
      [],
      "every live page must be reachable through the shared navigation, a contextual path, the sitemap, or an explicit workflow",
    );
    const providers = readFileSync(path.join(root, "routes", "providers.tsx"), "utf8");
    assert.match(providers, /to:\s*"\/requests\/\$id"/, "provider requests must connect to their status route");
    assert.ok(!entryPaths.has("/requests/$id"), "workflow-only request status is not a public navigation destination");
  });

  it("the public sitemap contains only live Hami routes", () => {
    const sitemap = readFileSync(path.join(root, "..", "public", "sitemap.xml"), "utf8");
    const paths = [...sitemap.matchAll(/<loc>https:\/\/haminp\.vercel\.app([^<]*)<\/loc>/g)]
      .map((match) => match[1] || "/");
    assert.equal(new Set(paths).size, paths.length, "sitemap contains duplicate routes");
    const resolveFeature = (route: string) =>
      registry.features.find((feature: { route: string }) => feature.route === route) ??
      registry.features.find((feature: { route: string }) => {
        const pattern = feature.route.split("/");
        const candidate = route.split("/");
        return pattern.length === candidate.length &&
          pattern.every((segment, index) => segment.startsWith("$") ? candidate[index].length > 0 : segment === candidate[index]);
      });
    const inactive = paths.filter((route) => resolveFeature(route)?.status !== "live");
    assert.deepEqual(inactive, [], `sitemap lists hidden/archived/unregistered paths: ${inactive.join(", ")}`);
    assert.ok(!paths.includes("/contact"), "closed contact surface must not be presented as an active search destination");
    assert.ok(!paths.includes("/terms"), "noindex Terms page must not be advertised in the sitemap");
    assert.ok(!paths.includes("/privacy"), "noindex Privacy page must not be advertised in the sitemap");
  });

  it("active service pages never route visitors to the closed contact surface", () => {
    for (const file of ["src/routes/services.$slug.tsx", "src/routes/group.businesses.tsx"]) {
      const source = readFileSync(path.join(root, "..", file), "utf8");
      assert.ok(!source.includes('to="/contact"'), `${file} links to a contact surface that is currently inactive`);
    }
    assert.ok(readFileSync(path.join(root, "..", "src/components/pages/project-inquiry-cta.tsx"), "utf8").includes('to="/domain"'));
  });

  it("makes the owner ForgeBot query workspace reachable and truth-labeled", () => {
    const owner = readFileSync(path.join(root, "routes", "owner.tsx"), "utf8");
    const forgeConsole = readFileSync(path.join(root, "components", "forge", "forge-console.tsx"), "utf8");
    assert.ok(owner.includes('id="forgebot-workspace"'));
    assert.ok(owner.includes("<ForgeConsoleWidgets apiKey={key} />"));
    assert.ok(owner.includes("Your Hami workspace"));
    assert.ok(owner.includes("Let's work through Hami together."));
    assert.ok(owner.includes("Current Hami snapshot"));
    assert.ok(owner.includes("Refresh status"));
    assert.ok(owner.includes('id="more-owner-tools"'));
    assert.ok(owner.includes("Open tools"));
    assert.ok(owner.indexOf('id="forgebot-workspace"') < owner.indexOf('id="more-owner-tools"'));
    assert.ok(forgeConsole.includes('fetch("/api/ai/status"'));
    assert.ok(forgeConsole.includes('fetch("/api/forge/ask"'));
    assert.ok(forgeConsole.includes("Talk to ForgeBot"));
    assert.ok(forgeConsole.includes("Advanced tools (optional)"));
    assert.ok(forgeConsole.includes("ForgeBot is in simple test mode"));
    assert.ok(forgeConsole.includes("memories_used"));
    assert.ok(forgeConsole.includes("ForgeBot’s answer"));
    assert.ok(forgeConsole.includes("ForgeBot's answer is a guide, not proof"));
    assert.ok(forgeConsole.includes('providerName === "openai"'));
    assert.ok(forgeConsole.includes("zero-spend default"));
    assert.ok(!forgeConsole.includes("localStorage"));
    assert.ok(!forgeConsole.includes("sessionStorage"));
    assert.ok(owner.includes('id="hami-frontier"'));
    assert.ok(owner.includes('id="hami-intelligence"'));
    assert.ok(owner.includes('id="owner-inquiries"'));
    assert.ok(owner.includes('id="owner-products-payments"'));
  });

  it("connects the private owner and operating consoles without adding them to public navigation", () => {
    const owner = readFileSync(path.join(root, "routes", "owner.tsx"), "utf8");
    const operations = readFileSync(path.join(root, "routes", "operations.tsx"), "utf8");
    assert.ok(owner.includes('to="/operations"'), "owner console must link to operating controls");
    assert.ok(operations.includes('to="/owner"'), "operating dashboard must link back to owner console");
    const publicNavRoutes: string[] = NAV.map((item) => item.to);
    assert.ok(!publicNavRoutes.includes("/owner") && !publicNavRoutes.includes("/operations"));
    for (const route of ["/owner", "/operations"]) {
      assert.ok(
        registry.features.some((feature: { route: string; status: string }) => feature.route === route && feature.status === "hidden"),
        `${route} must remain private from public discovery`,
      );
    }
  });

  it("connects orchestrator, distribution and payment configuration inside the private owner cockpit", () => {
    const owner = readFileSync(path.join(root, "routes", "owner.tsx"), "utf8");
    assert.ok(owner.includes('"/api/orchestrate/overview?limit=25&data_scope=REAL"'));
    assert.ok(owner.includes('"/api/products/channels"'));
    assert.ok(owner.includes('"/api/payments/status"'));
    assert.ok(owner.includes("actual_revenue_by_currency") && owner.includes("Verified outcome revenue · NPR"), "owner console must show verified NPR separately from USD");
    assert.ok(owner.includes("configuration_only"), "payment visibility must be explicitly configuration-only");
    assert.ok(owner.includes("conversion_count"), "distribution funnel rollups must use persisted channel counters");
    assert.ok(!owner.includes('"/api/payments/esewa/checkout"'), "owner overview must not initiate checkout");
    assert.ok(!owner.includes('"/api/payments/khalti/initiate"'), "owner overview must not initiate a payment");
  });

  it("wires owner pipeline detail and guarded actions while excluding contact-ledger data", () => {
    const owner = readFileSync(path.join(root, "routes", "owner.tsx"), "utf8");
    const api = readFileSync(path.join(root, "..", "backend", "app", "api", "orchestrator.py"), "utf8");
    for (const endpoint of [
      "/api/orchestrate/flow/",
      'runPipelineAction("advance"',
      'runPipelineAction("approve"',
      'runPipelineAction("execute"',
      'runPipelineAction("reject"',
      'runPipelineAction("product"',
      'runPipelineAction("next-decision"',
    ]) assert.ok(owner.includes(endpoint), "pipeline is missing endpoint/action " + endpoint);
    assert.ok(owner.includes('        "outcome",'), "actual interview results must use the guarded outcome endpoint");
    assert.ok(owner.includes("parseOutcomeRespondents"), "actual respondent rows must be validated");
    assert.ok(owner.includes("pseudonymous IDs"), "outcome capture must minimize contact data");
    assert.ok(owner.includes('type RespondentStage = "lead" | "contacted" | "interested"'), "interview capture must use the stages the backend can truthfully record");
    assert.ok(owner.includes("Owner-reported outcome saved as MOCK/REPORTED"), "owner-entered notes must not be presented as verified reality");
    assert.ok(owner.includes("outcome.source_kind") && owner.includes("outcome.verification_state"), "detail must show outcome provenance");
    assert.ok(owner.includes("separate verified ACTUAL_REVENUE outcome"), "paid-customer status requires verified revenue");
    assert.ok(!owner.includes('"/api/products/pipeline"'), "owner cockpit must not fetch the contact-rich product pipeline");
    assert.ok(api.includes('result.pop("customer_events", None)'), "detail/action responses must exclude customer ledger rows");
  });
  it("connects existing products to review, approval, and guarded publication without creating duplicates", () => {
    const owner = readFileSync(path.join(root, "routes", "owner.tsx"), "utf8");
    const productsApi = readFileSync(path.join(root, "..", "backend", "app", "api", "products.py"), "utf8");
    const engine = readFileSync(path.join(root, "..", "backend", "app", "services", "product_engine.py"), "utf8");
    assert.ok(owner.includes('"/api/products/" + product.id + "/prepare-offer-review"'));
    assert.ok(owner.includes('"/api/products/" + product.id + "/offer-approval"'));
    assert.ok(owner.includes('status: "launched", launch_state: "public"'));
    assert.ok(owner.includes("NPR 5000 one-time"));
    assert.ok(productsApi.includes('"/{product_id}/prepare-offer-review"'));
    assert.ok(engine.includes("An explicitly approved offer brief is required before launch"));
    assert.ok(engine.includes("Offer details changed after approval; review is required again."));
  });
  it("wires public offer checkout to durable provider intents and a noindex result page", () => {
    const home = readFileSync(path.join(root, "routes", "index.tsx"), "utf8");
    const result = readFileSync(path.join(root, "routes", "payment-result.tsx"), "utf8");
    const storage = readFileSync(path.join(root, "lib", "checkout-attempt-storage.ts"), "utf8");
    const api = readFileSync(path.join(root, "..", "backend", "app", "api", "payments.py"), "utf8");
    const engine = readFileSync(path.join(root, "..", "backend", "app", "services", "payment_intent_engine.py"), "utf8");
    assert.ok(home.includes("/api/payments/offers"));
    assert.ok(home.includes("/api/payments/products/") && home.includes("/checkout"));
    assert.ok(home.includes("Idempotency-Key"));
    assert.ok(home.includes('payload.checkout.type === "form_post"') && home.includes("form.submit()"));
    assert.ok(home.includes("Retry the same checkout attempt"));
    assert.ok(home.includes("onClick={() => void beginCheckout(offer, provider)}"));
    assert.ok(home.includes("error?.offerId === offer.id && error.retryable") && home.includes("beginCheckout(offer, error.provider)"), "only the failed offer may retry with its original provider");
    assert.ok(home.includes('from "@/lib/checkout-attempt-storage"') && home.includes("readStoredCheckoutAttempt"));
    assert.ok(storage.includes("export function writeStoredCheckoutAttempt") && storage.includes("export function clearStoredCheckoutAttempt"));
    assert.ok(storage.includes("export function createCheckoutAttemptKey") && storage.includes("getRandomValues"));
    assert.ok(storage.includes('state: "unavailable"') && storage.includes('state: "invalid"'), "unreadable or malformed storage is not reported as an empty slot");
    assert.ok(!home.includes("Math.random()"), "payment idempotency keys never use pseudo-random fallback");
    assert.ok(storage.includes("storage.getItem(key) === null"), "a clear requires read-back proof");
    assert.ok(home.includes("if (!writeStoredCheckoutAttempt(offer.id, attempt))") && home.includes("No checkout request was sent."), "checkout fails closed before fetch if the idempotency key cannot persist");
    assert.ok(
      home.indexOf("if (!writeStoredCheckoutAttempt(offer.id, attempt))") <
        home.indexOf('const response = await fetch("/api/payments/products/" + offer.id + "/checkout"'),
      "storage failure must be checked before the checkout POST",
    );
    assert.ok(home.includes("existingProvider !== provider"), "an unresolved attempt may not switch providers");
    assert.ok(!home.includes("delete next[offer.id]"), "ambiguous checkout failures must retain the idempotency key to avoid duplicate payment intents");
    assert.ok(result.includes('createFileRoute("/payment-result")'));
    assert.ok(result.includes('name: "robots", content: "noindex,nofollow,noarchive"'));
    assert.ok(result.includes('record?.status === "VERIFIED"'));
    assert.ok(result.includes("record?.fulfilled") && result.includes("not yet recorded as realized revenue"));
    const owner = readFileSync(path.join(root, "routes", "owner.tsx"), "utf8");
    assert.ok(owner.includes("<PaymentFulfillmentQueue apiKey={key} />"));
    assert.ok(api.includes('"/owner/fulfillment-queue"') && api.includes('"/owner/intents/{intent_id}/fulfill"'));
    assert.ok(engine.includes("def fulfill_verified_intent") && engine.includes("pending_fulfillment_intents"));
    assert.ok(api.includes('"/products/{product_id}/checkout"'));
    assert.ok(api.includes('"/intent/{public_ref}/reconcile"') && api.includes('"/products/{product_id}/checkout/reconcile"'), "provider-confirmed recovery is reachable from result and checkout-error paths");
    assert.ok(engine.includes("reconcile_public_intent") && engine.includes("reconcile_checkout_by_key") && engine.includes("retry_allowed"), "a new attempt requires server-side provider reconciliation");
    assert.ok(home.includes("reconcileCheckout") && home.includes("clearStoredCheckoutAttempt") && home.includes("payload.retry_allowed"), "the offer screen clears its key only after backend authorization");
    assert.ok(result.includes("/reconcile") && result.includes("clearStoredCheckoutAttempt(payload.offer_id)") && result.includes("retry_allowed"), "the result page shares the fail-closed clear contract");
    assert.ok(result.includes("payload.retry_allowed === true && recovery.retry_allowed === true"), "retry permission requires both server-side fields to agree");
    assert.ok(result.includes('from "@/lib/checkout-attempt-storage"'));
    assert.ok(
      result.indexOf("if (allowed && !clearStoredCheckoutAttempt(payload.offer_id))") < result.indexOf("setRetryAllowed(allowed)"),
      "retry permission must remain blocked until local attempt identity is verified cleared",
    );
    assert.ok(home.includes("if (!clearStoredCheckoutAttempt(offer.id))"), "the offer page also blocks retries when deletion cannot be verified");

    assert.ok(engine.includes("finalize_esewa_callback") && engine.includes("finalize_khalti_callback"));
  });

  it("keeps the operating model, scout queue, and buyer-journey tools connected to their guarded APIs", () => {
    const owner = readFileSync(path.join(root, "routes", "owner.tsx"), "utf8");
    const controls = [
      {
        mount: "<OperatingV4 apiKey={key} />",
        file: path.join(root, "components", "owner", "operating-v4.tsx"),
        apiPrefix: "/api/opv4/",
        backend: path.join(root, "..", "backend", "app", "api", "operating_v4.py"),
        prefix: '/opv4',
      },
      {
        mount: "<ScoutQueue apiKey={key} />",
        file: path.join(root, "components", "owner", "scout-queue.tsx"),
        apiPrefix: "/api/scout/",
        backend: path.join(root, "..", "backend", "app", "api", "scout.py"),
        prefix: '/scout',
      },
      {
        mount: "<PurchaseJourney apiKey={key} />",
        file: path.join(root, "components", "owner", "purchase-journey.tsx"),
        apiPrefix: "/api/residue/",
        backend: path.join(root, "..", "backend", "app", "api", "residue.py"),
        prefix: '/residue',
      },
    ] as const;
    for (const control of controls) {
      assert.ok(owner.includes(control.mount), `owner console must mount ${control.mount}`);
      const component = readFileSync(control.file, "utf8");
      assert.match(component, /X-API-Key.*key/);
      assert.ok(component.includes(control.apiPrefix) && component.includes("${path}"), `${control.mount} must call its canonical API`);
      const backend = readFileSync(control.backend, "utf8");
      assert.ok(backend.includes(`prefix="${control.prefix}"`), `${control.prefix} router must remain registered at its canonical prefix`);
      assert.ok(backend.includes("security.require_owner_api_key(request)"), `${control.prefix} endpoints must retain owner-key enforcement`);
    }
  });

  it("connects owner research tasks to guarded task-event provenance", () => {
    const owner = readFileSync(path.join(root, "routes", "owner.tsx"), "utf8");
    const backend = readFileSync(path.join(root, "..", "backend", "app", "api", "forge.py"), "utf8");
    assert.ok(owner.includes("tasks/${taskId}/history"), "task history must reuse the existing Forge API");
    assert.ok(owner.includes("X-API-Key"), "task history must use the owner-key client");
    assert.ok(owner.includes("taskHistoryById") && owner.includes("UNKNOWN — task history is not available on this backend."), "unavailable history must remain explicitly unknown");
    assert.ok(owner.includes("summarizeTaskEventDetails") && owner.includes("error details withheld"), "event details must use the bounded summary");
    assert.ok(owner.includes("Evidence refs") && owner.includes("Attempts"), "task provenance and retry state must be visible");
    assert.ok(backend.includes('@router.get("/tasks/{task_id}/history"'), "the canonical event-history endpoint must remain registered");
    assert.ok(backend.includes("require_owner_api_key(request)"), "the research router must retain owner-key enforcement");
  });

  it("connects persisted partial-cycle truth to the private owner cockpit", () => {
    const owner = readFileSync(path.join(root, "routes", "owner.tsx"), "utf8");
    assert.ok(owner.includes("partial_cycles"), "owner cockpit must read partial-run totals");
    assert.ok(owner.includes('"Cycle outcomes"'), "owner cockpit must expose aggregate cycle health");
    assert.ok(
      owner.includes('cycle.status === "PARTIAL"') && owner.includes('"text-warning"'),
      "partial-run notes must be warnings, not hard-failure errors",
    );
    assert.ok(owner.includes("stage_partials"), "owner summary contract must include persisted partial stages");
  });

  it("does not advertise the hidden, closed intake route from the public Businesses page", () => {
    const businessesPage = readFileSync(path.join(root, "routes", "group.businesses.tsx"), "utf8");
    assert.ok(!businessesPage.includes('to="/forge-bot-intake"'));
    assert.match(businessesPage, /Online inquiries remain closed/);
    for (const target of ['to="/services"', 'to="/process"', 'to="/domain"']) {
      assert.ok(businessesPage.includes(target), `closed intake state must route to a live Hami path: ${target}`);
    }
    const intakeFeature = registry.features.find((feature: { route: string }) => feature.route === "/forge-bot-intake");
    assert.equal(intakeFeature?.status, "hidden");
  });

  it("owner-only, TEST-only and closed intake surfaces remain hidden", () => {
    const status = (route: string) => registry.features.find((feature: { route: string }) => feature.route === route)?.status;
    for (const route of ["/owner", "/operations", "/prototype/inbox", "/bot-qualification-demo", "/forge-bot-intake", "/request", "/contact"]) {
      assert.equal(status(route), "hidden", `${route} must stay out of public discovery`);
    }
    for (const route of ["/climb", "/what-we-learned", "/work", "/request-a-project"]) {
      assert.equal(status(route), "archived", `${route} should remain a compatibility redirect, not a parallel surface`);
    }
  });

  it("strategic pages and request status close back into the same Hami pathways", () => {
    const routes = [
      ["technology.tsx", "technology"],
      ["ventures.tsx", "ventures"],
      ["requests.$id.tsx", "requestStatus"],
    ] as const;
    for (const [file, key] of routes) {
      const source = readFileSync(path.join(root, "routes", file), "utf8");
      assert.ok(
        source.includes(`HamiPathways current="${key}"`),
        `${file} is missing its canonical Hami pathway`,
      );
    }
  });

  it("legal copy does not direct visitors to closed contact", () => {
    const terms = readFileSync(path.join(root, "..", "src", "routes", "terms.tsx"), "utf8");
    assert.ok(!terms.includes('href="/contact"'));
    assert.ok(terms.includes('href="/services"'));
    assert.ok(terms.includes("currently closed"));
  });

  it("serves the schema referenced by the public feature registry", () => {
    const schemaPath = path.join(root, "..", "public", "features.schema.json");
    assert.ok(existsSync(schemaPath), "public/features.schema.json is missing");
    const schema = JSON.parse(readFileSync(schemaPath, "utf8"));
    assert.equal(registry.$schema, schema.$id);
    assert.equal(schema.$id, "https://haminp.vercel.app/features.schema.json");
    assert.equal(schema.$defs.feature.properties.status.enum.join(","), "live,hidden,archived,planned");
  });

  it("registry entries are well-formed", () => {
    for (const f of registry.features) {
      assert.ok(f.id && f.name && f.intent && f.route, `feature missing fields: ${JSON.stringify(f)}`);
      assert.match(f.status, /^(live|hidden|archived|planned)$/, `bad status on ${f.id}`);
      assert.ok(f.date_added && f.commit, `missing provenance on ${f.id}`);
    }
    const ids = registry.features.map((f: { id: string }) => f.id);
    assert.equal(new Set(ids).size, ids.length, "duplicate feature ids");
  });
  it("keeps investigation open-ended while bounding real-world intervention", () => {
    const operatingModel = readFileSync(path.join(root, "..", "docs", "OPERATING_MODEL.md"), "utf8").replace(/\s+/g, " ");
    assert.ok(operatingModel.includes("Investigation is open-ended even while interventions are bounded."));
    assert.ok(operatingModel.includes("90-day window is a review horizon, not an obligation to keep a disproven"));
    assert.ok(operatingModel.includes("Broad exploration does not authorize parallel"));
    assert.ok(operatingModel.includes("Revenue is one possible value outcome, not a gate on what Hami may investigate."));
  });

  it("preserves Hami's owner-approved value-domain invariant separately from the current pilot", () => {
    const agents = readFileSync(path.join(root, "..", "AGENTS.md"), "utf8");
    const blueprint = readFileSync(path.join(root, "..", "FORGE_SUBSTRATE_BLUEPRINT.md"), "utf8");
    const readme = readFileSync(path.join(root, "..", "README.md"), "utf8");
    const systemMap = readFileSync(path.join(root, "..", "docs", "HAMI_SYSTEM_MAP.md"), "utf8");
    const home = readFileSync(routeFile("/"), "utf8");
    assert.ok(agents.includes("Hami's domain is **value itself**"));
    assert.ok(blueprint.includes("Universal Value Intelligence & Action System"));
    assert.ok(blueprint.includes("do not define the full domain of Hami"));
    assert.ok(readme.includes("Examples and present capabilities are not the boundary"));
    assert.ok(systemMap.includes("Foundational scope: value itself"));
    assert.ok(home.includes("These instruments are not a boundary"));
  });

});
