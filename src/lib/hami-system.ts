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
