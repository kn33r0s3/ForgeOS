import { Link } from "@tanstack/react-router";
import { SITE } from "@/lib/content";
import { BrandMark } from "./brand-mark";
import { Container } from "./container";
import { Eyebrow } from "./eyebrow";

const GROUP_LINKS = [
  { label: "Network feed", to: "/feed" },
  { label: "Search services", to: "/providers" },
  { label: "Service categories", to: "/services" },
  { label: "How it works", to: "/about" },
  { label: "Contact", to: "/contact" },
] as const;

const WORK_LINKS = [
  { label: "Open network", to: "/feed" },
  { label: "Service categories", to: "/services" },
  { label: "Providers", to: "/providers" },
] as const;

export function SiteFooter() {
  const year = new Date().getFullYear();
  return (
    <footer className="mt-auto border-t border-line bg-card">
      <Container className="grid gap-10 py-16 sm:grid-cols-2 lg:grid-cols-4">
        <div className="sm:col-span-2 lg:col-span-1">
          <BrandMark />
          <p className="mt-4 max-w-xs text-sm leading-relaxed text-muted">
            Hami is one system. Services are one recorded path through it when public listings and contact routes are available. Nepal is where that path starts.
          </p>
        </div>
        <div className="flex flex-col gap-3">
          <Eyebrow className="mb-1" tone="muted">
            Explore
          </Eyebrow>
          {GROUP_LINKS.map((item) => (
            <Link
              key={item.to}
              to={item.to}
              className="text-sm text-muted transition-colors duration-150 hover:text-accent"
            >
              {item.label}
            </Link>
          ))}
        </div>
        <div className="flex flex-col gap-3">
          <Eyebrow className="mb-1" tone="muted">
            Quick links
          </Eyebrow>
          {WORK_LINKS.map((item) => (
            <Link
              key={item.to}
              to={item.to}
              className="text-sm text-muted transition-colors duration-150 hover:text-accent"
            >
              {item.label}
            </Link>
          ))}
        </div>
        <div className="flex flex-col gap-3">
          <Eyebrow className="mb-1" tone="muted">
            Connect
          </Eyebrow>
          <Link
            to="/feed"
            className="text-sm text-muted transition-colors duration-150 hover:text-accent"
          >
            Explore the network
          </Link>
          {SITE.email ? (
            <a href={`mailto:${SITE.email}`} className="text-sm text-muted transition-colors duration-150 hover:text-accent">
              {SITE.email}
            </a>
          ) : <span className="text-sm text-muted">Contact mailbox pending</span>}
          {SITE.url ? (
            <a href={SITE.url} className="text-sm text-muted transition-colors duration-150 hover:text-accent">
              {SITE.domain}
            </a>
          ) : <span className="text-sm text-muted">{SITE.domain}</span>}
        </div>
      </Container>
      <Container className="flex flex-col gap-2 border-t border-line py-5 font-mono text-micro uppercase tracking-[0.12em] text-dim sm:flex-row sm:items-center sm:justify-between">
        <span>
          © {year} {SITE.name}
        </span>
        <span>
          {SITE.name} · {SITE.domain}
        </span>
        <span>{SITE.location}</span>
      </Container>
    </footer>
  );
}
