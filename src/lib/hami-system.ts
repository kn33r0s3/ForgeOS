/**
 * Canonical public navigation for Hami.
 * Put public routes in this shared map instead of maintaining competing
 * header/footer lists. Private tools and TEST-only routes stay separate.
 */
export const NAV = [
  { label: "Home", to: "/" },
  { label: "Findings", to: "/discoveries" },
  { label: "Unknowns", to: "/unknowns" },
  { label: "Network", to: "/feed" },
  { label: "Experiments", to: "/experiments" },
  { label: "Services", to: "/services" },
  { label: "Group", to: "/group" },
  { label: "About", to: "/about" },
] as const;

export const FOOTER_GROUPS = [
  {
    title: "The system",
    items: [
      { label: "About Hami", to: "/about" },
      { label: "The group", to: "/group" },
      { label: "How we work", to: "/process" },
      { label: "Technology", to: "/technology" },
      { label: "Ventures", to: "/ventures" },
    ],
  },
  {
    title: "Evidence & decisions",
    items: [
      { label: "Findings", to: "/discoveries" },
      { label: "Open unknowns", to: "/unknowns" },
      { label: "Network", to: "/feed" },
      { label: "Opportunities", to: "/opportunities" },
      { label: "Action state", to: "/actions" },
      { label: "Experiments", to: "/experiments" },
    ],
  },
  {
    title: "Work & value",
    items: [
      { label: "Hami services", to: "/services" },
      { label: "Verified providers", to: "/providers" },
      { label: "Public work board", to: "/domain" },
      { label: "The missed inquiry", to: "/needs" },
    ],
  },
  {
    title: "Account & trust",
    items: [
      { label: "Personal context", to: "/system" },
      { label: "Sign in", to: "/login" },
      { label: "Privacy", to: "/privacy" },
      { label: "Terms", to: "/terms" },
    ],
  },
] as const;

export const SYSTEM_PATHWAYS = {
  home: [
    { label: "Read findings", to: "/discoveries" },
    { label: "Inspect unknowns", to: "/unknowns" },
    { label: "Open network records", to: "/feed" },
    { label: "See experiments", to: "/experiments" },
    { label: "Explore services", to: "/services" },
    { label: "Open the work board", to: "/domain" },
  ],
  findings: [
    { label: "Related network records", to: "/feed" },
    { label: "Questions still open", to: "/unknowns" },
    { label: "Tests and outcomes", to: "/experiments" },
  ],
  unknowns: [
    { label: "Source observations", to: "/discoveries" },
    { label: "Connected records", to: "/feed" },
    { label: "Experiments and outcomes", to: "/experiments" },
  ],
  network: [
    { label: "Review findings", to: "/discoveries" },
    { label: "Opportunity hypotheses", to: "/opportunities" },
    { label: "Public work board", to: "/domain" },
    { label: "Verified providers", to: "/providers" },
  ],
  opportunities: [
    { label: "Evidence behind the question", to: "/discoveries" },
    { label: "Open unknowns", to: "/unknowns" },
    { label: "Experiments", to: "/experiments" },
    { label: "Recorded action state", to: "/actions" },
  ],
  experiments: [
    { label: "Open unknowns", to: "/unknowns" },
    { label: "Collected evidence", to: "/discoveries" },
    { label: "Action state", to: "/actions" },
    { label: "The current field test", to: "/needs" },
  ],
  services: [
    { label: "How Hami works", to: "/process" },
    { label: "Verified external providers", to: "/providers" },
    { label: "Public work board", to: "/domain" },
    { label: "Group context", to: "/group" },
  ],
  providers: [
    { label: "Hami's own service offers", to: "/services" },
    { label: "Public work board", to: "/domain" },
    { label: "Connected network", to: "/feed" },
  ],
  work: [
    { label: "Verified providers", to: "/providers" },
    { label: "Connected public records", to: "/feed" },
    { label: "Opportunity hypotheses", to: "/opportunities" },
    { label: "Hami services", to: "/services" },
  ],
  needs: [
    { label: "Experiment log", to: "/experiments" },
    { label: "Questions to resolve", to: "/unknowns" },
    { label: "Public work board", to: "/domain" },
  ],
  actions: [
    { label: "Opportunity hypotheses", to: "/opportunities" },
    { label: "Experiments", to: "/experiments" },
    { label: "Evidence trail", to: "/feed" },
  ],
  about: [
    { label: "Findings", to: "/discoveries" },
    { label: "Open unknowns", to: "/unknowns" },
    { label: "Experiments", to: "/experiments" },
    { label: "How we work", to: "/process" },
  ],
  group: [
    { label: "Hami services", to: "/services" },
    { label: "How we work", to: "/process" },
    { label: "Technology", to: "/technology" },
    { label: "Ventures", to: "/ventures" },
  ],
  process: [
    { label: "Hami services", to: "/services" },
    { label: "Public work board", to: "/domain" },
    { label: "The group", to: "/group" },
  ],
  technology: [
    { label: "How Hami works", to: "/process" },
    { label: "Current technical services", to: "/services" },
    { label: "Public work and needs", to: "/domain" },
    { label: "Connected evidence", to: "/feed" },
  ],
  ventures: [
    { label: "Current work Hami can do", to: "/services" },
    { label: "Work and needs", to: "/domain" },
    { label: "Opportunity hypotheses", to: "/opportunities" },
    { label: "The unified group", to: "/group" },
  ],
  requestStatus: [
    { label: "Verified providers", to: "/providers" },
    { label: "Hami service catalogue", to: "/services" },
    { label: "Public work board", to: "/domain" },
  ],
} as const;

export type SystemSurface = keyof typeof SYSTEM_PATHWAYS;

/** Every public pathway below must have a matching live feature-registry entry. */
export const PUBLIC_SYSTEM_PATHS = [
  "/",
  "/discoveries",
  "/unknowns",
  "/feed",
  "/opportunities",
  "/actions",
  "/experiments",
  "/services",
  "/services/$slug",
  "/group",
  "/group/businesses",
  "/process",
  "/technology",
  "/ventures",
  "/providers",
  "/domain",
  "/needs",
  "/about",
  "/system",
  "/requests/$id",
  "/terms",
  "/privacy",
] as const;
