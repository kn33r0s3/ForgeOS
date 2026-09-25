export const SITE = {
  name: "Forge",
  legalName: "Forge",
  domain: "Domain pending verification",
  url: "",
  email: "hello@pending-domain.local",
  location: "Starting in Nepal",
  tagline: "A network of real work, evidence, and outcomes.",
  description:
    "Forge is a world of record. People, organizations, capabilities, needs, work, services, offers, trades, and outcomes stay in one network. Verified services are one path that is usable now. Nepal is the first geography, not the boundary of the system.",
} as const;

export const NAV = [
  { label: "Home", to: "/" },
  { label: "Services", to: "/services" },
  { label: "Providers", to: "/providers" },
  { label: "Work", to: "/domain" },
  { label: "Discoveries", to: "/discoveries" },
  { label: "How it works", to: "/about" },
  { label: "Contact", to: "/contact" },
] as const;

export const providerCategories = ["All"] as const;

export type PublicServiceListing = {
  id: number;
  provider_id: number;
  title: string;
  description: string;
  category?: string | null;
  location?: string | null;
  price_from?: string | null;
  currency?: string | null;
  availability_status?: string | null;
  is_active?: boolean;
  public_visible?: boolean;
};

export type ProviderRecord = {
  id: number;
  slug: string;
  name: string;
  category: string;
  location: string;
  response: string;
  price: string;
  verified: boolean;
  summary: string;
  service: string;
  listings: PublicServiceListing[];
  status?: string;
  launchState?: string | null;
  actualCustomers: number;
  actualRevenue: number;
  actualCost: number;
  leadCount: number;
  paidCustomerCount: number;
};

export const providers: ProviderRecord[] = [];

export type PublicDiscovery = {
  id: number;
  source: string;
  title?: string | null;
  excerpt: string;
  canonical_url?: string | null;
  retrieved_at?: string | null;
  epistemic_state: string;
  freshness?: string;
};

export type PublicDomainRecord = {
  id: number;
  kind: "job" | "offer" | "trade";
  title: string;
  detail: string;
  city?: string | null;
  stated_price?: string | null;
  status: string;
  terms_complete?: boolean;
  created_at?: string;
};

export type PublicMatchCandidate = {
  kind: string;
  id: number;
  name: string;
  where?: string | null;
  stated_price?: string | null;
  stated_availability?: string | null;
  reasons: string[];
  unknowns: string[];
  connection_id?: number | null;
  latest_response?: string | null;
};

export type PublicMatch = {
  need_id: number;
  need_kind: string;
  need_title: string;
  need_city?: string | null;
  candidates: PublicMatchCandidate[];
  unknowns: string[];
};

export type PublicTrust = {
  subject_kind: string;
  subject_id: number;
  recorded_requests: number;
  reported_payments: Array<{ connection_id: number; amount: number; unit: string; verification: string }>;
  verified_payments: Array<{ connection_id: number; amount: number; unit: string; verification: string }>;
  disputed_payments: Array<{ connection_id: number; amount: number; unit: string; verification: string }>;
  settled_payments: Array<{ connection_id: number; amount: number; unit: string; verification: string }>;
  disputes: number;
  unknowns: string[];
};

export type PublicConnection = {
  id: number;
  left_kind: string;
  left_id: number;
  right_kind: string;
  right_id: number;
  state: string;
  reason: string;
  known?: string | null;
  unknown?: string | null;
  agreement_gap: string;
  forge_role: string;
  owns_either_side: boolean;
  latest_response?: string | null;
  latest_fulfillment?: string | null;
};

export async function recordPublicConnectionResponse(input: {
  recordId: number;
  connectionId: number;
  close_token: string;
  note: string;
}): Promise<PublicConnection | null> {
  return postPublicJson<PublicConnection>(
    `/domain/${input.recordId}/connections/${input.connectionId}/response`,
    { close_token: input.close_token, note: input.note },
  );
}

export type PublicAlert = {
  id: number;
  source: string;
  text: string;
  created_at?: string | null;
};

export type PublicDomainEvents = {
  record_id: number;
  payments: string[];
  disputes: string[];
  completions: number;
  unknowns: string[];
};

export type EngineHealth = {
  reachable: boolean;
  status?: string;
  cycle?: { id?: number; status?: string; ended_at?: string | null } | null;
};

export async function loadEngineHealth(): Promise<EngineHealth> {
  const bases = getPublicApiBase() ? [getPublicApiBase()] : [];
  const urls = [...bases.map((base) => `${base}/health`), "/api/health"];
  if (typeof window !== "undefined") {
    urls.push(`${window.location.origin}/api/health`);
  }
  for (const url of [...new Set(urls)]) {
    try {
      const response = await fetch(url, { headers: { Accept: "application/json" } });
      if (!response.ok) continue;
      const body = (await response.json()) as EngineHealth;
      return { reachable: true, status: body.status, cycle: body.cycle ?? null };
    } catch {
      continue;
    }
  }
  return { reachable: false };
}

function getPublicApiBase() {
  return (import.meta.env.VITE_FORGE_API_BASE as string | undefined)?.replace(/\/$/, "") ?? "";
}

function getPublicApiCandidates(path: string): string[] {
  const backendBase = getPublicApiBase();
  const relativePath = `/api/public${path}`;
  const candidates = [relativePath];
  if (backendBase) {
    candidates.unshift(`${backendBase}/public${path}`);
  }

  if (typeof window !== "undefined") {
    const origin = window.location.origin;
    const sameOrigin = `${origin}${relativePath}`;
    if (!candidates.includes(sameOrigin)) {
      candidates.push(sameOrigin);
    }
  }

  return [...new Set(candidates)];
}

async function fetchJson<T>(url: string): Promise<T | null> {
  try {
    const response = await fetch(url, { headers: { Accept: "application/json" } });
    if (!response.ok) {
      return null;
    }
    return (await response.json()) as T;
  } catch {
    return null;
  }
}

async function fetchJsonFromCandidates<T>(path: string): Promise<T | null> {
  for (const url of getPublicApiCandidates(path)) {
    const payload = await fetchJson<T>(url);
    if (payload !== null) {
      return payload;
    }
  }
  return null;
}

export async function loadDiscoveries(limit = 20): Promise<PublicDiscovery[]> {
  const payload = await fetchJsonFromCandidates<PublicDiscovery[]>(
    `/discoveries?limit=${encodeURIComponent(String(limit))}`,
  );
  return Array.isArray(payload) ? payload : [];
}

export async function loadPublicDomain(): Promise<PublicDomainRecord[]> {
  const payload = await fetchJsonFromCandidates<PublicDomainRecord[]>("/domain");
  return Array.isArray(payload) ? payload : [];
}

export async function loadPublicMatches(): Promise<PublicMatch[]> {
  const payload = await fetchJsonFromCandidates<PublicMatch[]>("/matches");
  return Array.isArray(payload) ? payload : [];
}

export async function loadPublicConnections(): Promise<PublicConnection[]> {
  const payload = await fetchJsonFromCandidates<PublicConnection[]>("/connections");
  return Array.isArray(payload) ? payload : [];
}

export async function loadPublicAlerts(limit = 20): Promise<PublicAlert[]> {
  const payload = await fetchJsonFromCandidates<PublicAlert[]>(`/alerts?limit=${limit}`);
  return Array.isArray(payload) ? payload : [];
}

export async function loadPublicTrust(subjectKind: "provider" | "domain_record", subjectId: number): Promise<PublicTrust | null> {
  return fetchJsonFromCandidates<PublicTrust>(`/trust/${subjectKind}/${subjectId}`);
}

export async function loadPublicDomainEvents(recordId: number): Promise<PublicDomainEvents | null> {
  return fetchJsonFromCandidates<PublicDomainEvents>(`/domain/${recordId}/events`);
}

async function postPublicJson<T>(path: string, body: unknown): Promise<T | null> {
  for (const url of getPublicApiCandidates(path)) {
    try {
      const response = await fetch(url, {
        method: "POST",
        headers: { "Content-Type": "application/json", Accept: "application/json" },
        body: JSON.stringify(body),
      });
      if (response.ok) {
        return (await response.json()) as T;
      }
    } catch {
      continue;
    }
  }
  return null;
}

export async function closePublicDomainRecord(input: {
  recordId: number;
  close_token: string;
  result: "completed" | "withdrawn" | "paid";
  note: string;
  amount_npr?: number | null;
}): Promise<PublicDomainRecord | null> {
  return postPublicJson<PublicDomainRecord>(`/domain/${input.recordId}/close`, {
    close_token: input.close_token,
    result: input.result,
    note: input.note,
    amount_npr: input.result === "paid" ? input.amount_npr : null,
  });
}

export async function disputePublicDomainRecord(input: {
  recordId: number;
  close_token: string;
  note: string;
}): Promise<PublicDomainEvents | null> {
  return postPublicJson<PublicDomainEvents>(`/domain/${input.recordId}/dispute`, {
    close_token: input.close_token,
    note: input.note,
  });
}

export async function createPublicDomainRecord(input: {
  kind: "job" | "offer" | "trade";
  title: string;
  detail: string;
  city?: string | null;
  stated_price?: string | null;
}): Promise<(PublicDomainRecord & { close_token: string }) | null> {
  for (const url of getPublicApiCandidates("/domain")) {
    const response = await fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json", Accept: "application/json" },
      body: JSON.stringify(input),
    });
    if (response.ok) {
      return (await response.json()) as PublicDomainRecord & { close_token: string };
    }
  }
  return null;
}

export async function loadProviders(filters?: { q?: string; category?: string; city?: string }): Promise<ProviderRecord[]> {
  const params = new URLSearchParams();
  if (filters?.q?.trim()) params.set("q", filters.q.trim());
  if (filters?.category && filters.category !== "All") params.set("category", filters.category);
  if (filters?.city?.trim()) params.set("city", filters.city.trim());
  const query = params.toString();
  const suffix = query ? `?${query}` : "";
  const servicePayload = await fetchJsonFromCandidates<Array<{
    id?: number;
    provider_id?: number;
    title?: string;
    description?: string;
    category?: string | null;
    location?: string | null;
    price_from?: string | null;
    currency?: string | null;
    availability_status?: string | null;
    public_visible?: boolean;
    is_active?: boolean;
  }>>(`/services${suffix}`);

  if (!Array.isArray(servicePayload)) {
    return [];
  }

  const providerMap = new Map<number, ProviderRecord>();
  const listingsMap = new Map<number, PublicServiceListing[]>();

  for (const item of servicePayload) {
    if (!item || typeof item.provider_id !== "number") {
      continue;
    }
    const listing: PublicServiceListing = {
      id: item.id ?? 0,
      provider_id: item.provider_id,
      title: item.title ?? "",
      description: item.description ?? "",
      category: item.category ?? "Service",
      location: item.location ?? null,
      price_from: item.price_from ?? null,
      currency: item.currency ?? "NPR",
      availability_status: item.availability_status ?? null,
      is_active: item.is_active ?? true,
      public_visible: item.public_visible ?? true,
    };
    const existing = listingsMap.get(item.provider_id) ?? [];
    existing.push(listing);
    listingsMap.set(item.provider_id, existing);
  }

  for (const url of getPublicApiCandidates(`/providers${suffix}`)) {
    const payload = await fetchJson<Array<{
      id?: number;
      name?: string;
      business_name?: string | null;
      category?: string | null;
      summary?: string | null;
      region?: string | null;
      city?: string | null;
      country?: string | null;
      website?: string | null;
      verification_status?: string | null;
      is_active?: boolean;
      public_visible?: boolean;
    }>>(url);

    if (!Array.isArray(payload)) {
      continue;
    }

    for (const item of payload) {
      const providerId = item.id ?? 0;
      const name = item.name ?? item.business_name ?? "";
      const summary = item.summary ?? "";
      const locationCandidate = [item.city, item.region].filter(Boolean).join(", ");
      const location = locationCandidate || "Location not recorded";
      const listings = listingsMap.get(providerId) ?? [];
      const primaryListing = listings[0];

      const record: ProviderRecord = {
        id: providerId,
        slug: `provider-${providerId}`,
        name,
        category: item.category || primaryListing?.category || "Service",
        location,
        response: primaryListing?.availability_status ? `Availability: ${primaryListing.availability_status}` : "Availability not recorded",
        price: primaryListing?.price_from ? `${primaryListing.price_from} ${primaryListing.currency ?? "NPR"}` : "Price not recorded",
        verified: (item.verification_status ?? "unverified") === "verified",
        summary,
        service: primaryListing?.title ?? summary,
        listings,
        status: primaryListing?.availability_status ?? undefined,
        launchState: undefined,
        actualCustomers: 0,
        actualRevenue: 0,
        actualCost: 0,
        leadCount: 0,
        paidCustomerCount: 0,
      };
      providerMap.set(providerId, record);
    }

    if (providerMap.size > 0) {
      return Array.from(providerMap.values());
    }
  }

  return [];
}

export async function createBookingRequest(input: {
  provider_id: number;
  service_listing_id?: number | null;
  requester_name: string;
  requester_phone?: string | null;
  requester_email?: string | null;
  requested_service: string;
  requested_date?: string | null;
  requested_time?: string | null;
  notes?: string | null;
}): Promise<{ id: number; status: string; provider_response?: string | null; requested_service: string } | null> {
  const candidateUrls = getPublicApiCandidates("/booking-requests");

  for (const url of candidateUrls) {
    const response = await fetch(url, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Accept: "application/json",
      },
      body: JSON.stringify(input),
    });

    if (!response.ok) {
      continue;
    }

    const payload = (await response.json()) as {
      id?: number;
      status?: string;
      provider_response?: string | null;
      requested_service?: string;
    };

    return {
      id: payload.id ?? 0,
      status: payload.status ?? "pending",
      provider_response: payload.provider_response ?? null,
      requested_service: payload.requested_service ?? input.requested_service,
    };
  }

  return null;
}

export type BookingStatus = {
  id: number;
  status: string;
  requested_service: string;
  provider_id?: number;
  provider_name?: string | null;
  requested_date?: string | null;
  requested_time?: string | null;
  provider_response?: string | null;
};

export async function getBookingRequestStatus(id: number): Promise<BookingStatus | null> {
  const candidateUrls = getPublicApiCandidates(`/booking-requests/${id}`);

  for (const url of candidateUrls) {
    const response = await fetch(url, {
      headers: { Accept: "application/json" },
    });

    if (!response.ok) {
      continue;
    }

    const payload = (await response.json()) as {
      id?: number;
      status?: string;
      requested_service?: string;
      provider_id?: number;
      provider_name?: string | null;
      requested_date?: string | null;
      requested_time?: string | null;
      provider_response?: string | null;
    };

    return {
      id: payload.id ?? id,
      status: payload.status ?? "pending",
      requested_service: payload.requested_service ?? "Service request",
      provider_id: payload.provider_id,
      provider_name: payload.provider_name ?? null,
      requested_date: payload.requested_date ?? null,
      requested_time: payload.requested_time ?? null,
      provider_response: payload.provider_response ?? null,
    };
  }

  return null;
}

export type NavHref = (typeof NAV)[number]["to"];

export type ServiceKind = "commercial";

export type Service = {
  number: string;
  slug: string;
  title: string;
  short: string;
  body: string;
  problem: string;
  does: string;
  deliverable: string;
  process: string;
  forWho: string;
  next: string;
};

export const services: Service[] = [
  {
    number: "01",
    slug: "software",
    title: "Software & web development",
    short: "Websites and web applications that support a real job to be done.",
    body: "Websites, web apps, and focused tools designed around the work they need to support.",
    problem:
      "A digital presence or application has to be more than a polished surface: it needs to help someone find, decide, submit, manage, or operate.",
    does: "Forge shapes and builds focused web experiences, interfaces, and applications around the users, constraints, and workflows involved.",
    deliverable:
      "A scoped website or web application, responsive interface, documented handoff, and a clear path for future improvement.",
    process:
      "Understand the users and outcome → shape the smallest useful scope → build and review in visible steps → hand off clearly.",
    forWho:
      "Teams, founders, and operators who need a dependable website or focused application without unnecessary complexity.",
    next: "Share the situation, the people involved, and what the system needs to make easier.",
  },
  {
    number: "02",
    slug: "automation",
    title: "Business automation",
    short: "Practical automation for repeatable work and clearer handoffs.",
    body: "Reduce repeat work with practical automation, integrations, and clearer handoffs.",
    problem:
      "Repeated manual steps, disconnected tools, and unclear ownership create friction that compounds over time.",
    does: "Forge maps the current path, identifies safe opportunities to automate, and connects the smallest useful set of steps or systems.",
    deliverable:
      "A documented automation or integration, with boundaries, ownership, and an understandable fallback when automation should stop.",
    process:
      "Map the current work → choose the safe repeatable step → build and validate → document ownership and exceptions.",
    forWho:
      "Small teams and operators with recurring digital work that is stable enough to improve but not ready for a large platform.",
    next: "Describe the repeated task, the tools involved, and where errors or delays currently appear.",
  },
  {
    number: "03",
    slug: "operations",
    title: "Digital operations",
    short: "A clearer operating picture for work that is already happening.",
    body: "Turn scattered information and recurring tasks into an operating picture people can use.",
    problem:
      "Information is scattered across messages, documents, spreadsheets, and people, making status and next actions hard to see.",
    does: "Forge helps structure requests, decisions, handoffs, documentation, and lightweight operating routines around the work itself.",
    deliverable:
      "A practical operating flow, supporting documentation, and where appropriate a small digital surface that makes work visible.",
    process:
      "Understand the current operation → define the shared picture → introduce the smallest useful system → improve from use.",
    forWho:
      "Businesses and teams that need clearer execution, not a heavyweight enterprise transformation program.",
    next: "Bring one process that feels harder to run than it should be.",
  },
  {
    number: "04",
    slug: "internal-tools",
    title: "Internal tools",
    short: "Purposeful interfaces for teams, operators, and everyday decisions.",
    body: "Small, purposeful interfaces for teams, operators, and the decisions they make every day.",
    problem:
      "Generic tools can leave the important context buried, while custom systems can become oversized before anyone uses them.",
    does: "Forge designs focused internal tools around the decisions, states, and handoffs that matter to the team using them.",
    deliverable:
      "A focused internal interface or dashboard, with clear ownership and a maintainable scope.",
    process:
      "Listen to the operator → model the important states → prototype the useful path → build, test, and hand off.",
    forWho:
      "Teams with a defined internal workflow that needs more clarity than a document and less machinery than an ERP.",
    next: "Explain who uses the tool, what they need to see, and what action should follow.",
  },
  {
    number: "05",
    slug: "workflows",
    title: "Workflow systems",
    short: "Make the path from request to outcome easier to follow.",
    body: "Map the path from request to outcome, then make ownership and progress visible.",
    problem:
      "Work gets lost between intake, decisions, execution, and follow-up when no one can see the path or owns the next step.",
    does: "Forge turns a real workflow into visible stages, meaningful handoffs, and lightweight systems that help people move work forward.",
    deliverable:
      "A documented workflow model and, when useful, a supporting interface, automation, or dashboard.",
    process:
      "Understand the request → define stages and ownership → build the visible path → operate and improve it.",
    forWho:
      "Teams handling recurring requests, approvals, content, service work, or multi-step internal operations.",
    next: "Start with one workflow and identify where it currently pauses or disappears.",
  },
  {
    number: "06",
    slug: "support",
    title: "Technical support",
    short: "Calm, practical help when a system needs attention.",
    body: "Reliable technical thinking and hands-on help when a system needs attention.",
    problem:
      "A technical issue can block work even when the fix is small, especially when context and ownership are unclear.",
    does: "Forge investigates the stated problem, explains what is known, and helps with a focused fix or next step within the agreed scope.",
    deliverable:
      "A documented diagnosis, targeted correction where appropriate, and clear follow-up notes or recommendations.",
    process:
      "Reproduce or understand the issue → isolate the relevant surface → address or document the next step → confirm handoff.",
    forWho:
      "Small teams and owners who need a technically serious second pair of hands without a support theatre layer.",
    next: "Share the symptom, what changed, and what access or context is available.",
  },
];

export type ProcessStep = { number: string; title: string; body: string };

export const processSteps: ProcessStep[] = [
  {
    number: "01",
    title: "Understand",
    body: "Start with the real situation, constraints, and the outcome that would make the work better.",
  },
  {
    number: "02",
    title: "Build",
    body: "Shape the smallest useful version, then build in visible steps with clear decisions.",
  },
  {
    number: "03",
    title: "Operate",
    body: "Make the system understandable and usable in the context where the work actually happens.",
  },
  {
    number: "04",
    title: "Improve",
    body: "Learn from use, keep what works, and identify the next sensible improvement.",
  },
];

export type CapabilityKind = "commercial" | "prototype";

export type Capability = { name: string; kind: CapabilityKind; note: string };

export const capabilities: Capability[] = [
  {
    name: "Web applications",
    kind: "commercial",
    note: "Scoped websites and applications for a defined user and job.",
  },
  {
    name: "APIs & integrations",
    kind: "commercial",
    note: "Connecting the systems a team already uses, with clear boundaries.",
  },
  {
    name: "Automation",
    kind: "commercial",
    note: "Repeatable digital work made consistent, with a human fallback.",
  },
  {
    name: "Workflow design",
    kind: "commercial",
    note: "Visible stages, ownership, and the path from request to outcome.",
  },
  {
    name: "Dashboards",
    kind: "commercial",
    note: "Operating pictures that surface status and next action, not decoration.",
  },
  {
    name: "Business systems",
    kind: "commercial",
    note: "Small, maintainable software around a real internal process.",
  },
  {
    name: "Media & data processing",
    kind: "prototype",
    note: "Internal research and experiments. Not offered as a commercial product.",
  },
];

export type GroupAreaName =
  | "Technology"
  | "Digital Products"
  | "Operations"
  | "Commerce"
  | "Media"
  | "Infrastructure"
  | "Ventures";

export type GroupArea = {
  name: GroupAreaName;
  status: "strategic direction";
  description: string;
  href?: "/technology" | "/operations" | "/ventures";
};

export const groupAreas: GroupArea[] = [
  {
    name: "Technology",
    status: "strategic direction",
    description:
      "Systems, infrastructure, and technical foundations that make the wider group more capable.",
    href: "/technology",
  },
  {
    name: "Digital Products",
    status: "strategic direction",
    description:
      "Useful products and software built around real needs, with room to grow beyond a single project.",
  },
  {
    name: "Operations",
    status: "strategic direction",
    description:
      "Practical operating systems and disciplined execution across the work the group takes on.",
    href: "/operations",
  },
  {
    name: "Commerce",
    status: "strategic direction",
    description:
      "Future businesses and commercial activity developed with a clear operating foundation.",
  },
  {
    name: "Media",
    status: "strategic direction",
    description:
      "Media, content, and communication projects that help useful ideas travel further.",
  },
  {
    name: "Infrastructure",
    status: "strategic direction",
    description:
      "The underlying platforms and environments that support durable work.",
  },
  {
    name: "Ventures",
    status: "strategic direction",
    description:
      "A future home for experiments, partnerships, and new businesses when the evidence is right.",
    href: "/ventures",
  },
];

export type BusinessOffer = {
  title: string;
  problem: string;
  does: string;
  value: string;
  start: string;
};

export const currentOffers: BusinessOffer[] = [
  {
    title: "Build digital products",
    problem: "An idea needs a useful digital surface, but the right first version is unclear.",
    does: "Shape and build a focused website, web application, internal tool, or product surface around the real user and operating need.",
    value: "A usable, maintainable first release with a clear scope and an honest next step.",
    start: "Bring the idea, the intended user, and the job it should make easier.",
  },
  {
    title: "Develop business software",
    problem: "Important work is trapped in scattered documents, generic tools, or manual handoffs.",
    does: "Model the workflow and build the smallest software surface that makes states, decisions, and ownership clearer.",
    value: "Less ambiguity in daily work and a system that can be improved without starting over.",
    start: "Share one process that is expensive, slow, or difficult to see.",
  },
  {
    title: "Automate workflows",
    problem: "Repeatable digital work consumes time and creates avoidable errors.",
    does: "Map the current path, identify safe repeatable steps, and connect the relevant tools or actions.",
    value: "A more consistent workflow with documented boundaries and human control where it matters.",
    start: "Describe the repeated task, tools involved, and where it currently breaks.",
  },
  {
    title: "Operate technical systems",
    problem: "A technical system needs attention, but ownership, context, or the next action is unclear.",
    does: "Investigate a focused issue, improve the operating routine, and provide practical support within the agreed scope.",
    value: "Clearer technical ownership, fewer unknowns, and a dependable path to resolution.",
    start: "Send the symptom, what changed, and what context is available.",
  },
  {
    title: "Explore a new venture",
    problem: "A business idea needs technical and operational thinking before significant build-out.",
    does: "Help test the problem, shape a first operating model, and identify what should be built or learned next.",
    value: "A grounded decision about whether and how to move forward, without pretending the venture already exists.",
    start: "Start a strategic inquiry with the idea, uncertainty, and desired outcome.",
  },
];

export const trustPoints = [
  {
    number: "01",
    title: "Technical rigor",
    body: "Thoughtful systems that respect constraints, operators, and maintenance. Clean code is a delivery requirement, not a slogan.",
  },
  {
    number: "02",
    title: "Transparent process",
    body: "Plain language, visible scope, and no mystery about what happens next. Estimates are labelled as estimates.",
  },
  {
    number: "03",
    title: "Verifiable delivery",
    body: "Real work, honestly labelled. No invented clients, revenue, awards, or market share — anywhere on this platform.",
  },
] as const;

export const projectTypes = [
  "Business partnership",
  "Technology project",
  "Operational need",
  "Venture idea",
  "Strategic inquiry",
] as const;

export const timelines = ["Exploring", "Within 1 month", "1–3 months", "Flexible"] as const;

export function getService(slug: string): Service | undefined {
  return services.find((item) => item.slug === slug);
}

export function getGroupArea(name: string): GroupArea | undefined {
  return groupAreas.find((item) => item.name === name);
}

export const FORBIDDEN_PUBLIC_PATHS = ["/tools", "/tools/company-registration-fee", "/tools/pan-vat-guide"] as const;
