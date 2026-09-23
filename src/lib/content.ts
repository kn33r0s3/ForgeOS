export const SITE = {
  name: "Sanip Ops",
  legalName: "Sanip Operations",
  domain: "sanipoperations.com.np",
  url: "https://sanipoperations.com.np",
  email: "hello@sanipoperations.com.np",
  location: "Nepal · Remote-ready",
  tagline: "Build what lasts. Operate what matters.",
  description:
    "Sanip Ops is a parent operations and infrastructure group from Nepal. We design, build, and operate focused digital systems — and we are constructing the long-term platform those systems will live on.",
} as const;

export const NAV = [
  { label: "Services", to: "/services" },
  { label: "Group", to: "/group" },
  { label: "Businesses", to: "/group/businesses" },
  { label: "Technology", to: "/technology" },
  { label: "Operations", to: "/operations" },
  { label: "Ventures", to: "/ventures" },
  { label: "About", to: "/about" },
  { label: "Contact", to: "/contact" },
] as const;

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
    does: "Sanip Ops shapes and builds focused web experiences, interfaces, and applications around the users, constraints, and workflows involved.",
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
    does: "Sanip Ops maps the current path, identifies safe opportunities to automate, and connects the smallest useful set of steps or systems.",
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
    does: "Sanip Ops helps structure requests, decisions, handoffs, documentation, and lightweight operating routines around the work itself.",
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
    does: "Sanip Ops designs focused internal tools around the decisions, states, and handoffs that matter to the team using them.",
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
    does: "Sanip Ops turns a real workflow into visible stages, meaningful handoffs, and lightweight systems that help people move work forward.",
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
    does: "Sanip Ops investigates the stated problem, explains what is known, and helps with a focused fix or next step within the agreed scope.",
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
