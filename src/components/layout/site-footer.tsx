import { Link } from "@tanstack/react-router";
import { SITE } from "@/lib/content";
import { Container } from "./container";

const DISCOVERY_LINKS = [
  { label: "Sourced discoveries", to: "/discoveries" },
  { label: "Opportunities", to: "/opportunities" },
  { label: "Network", to: "/feed" },
] as const;

const ACTION_LINKS = [
  { label: "Work board", to: "/domain" },
  { label: "Verified providers", to: "/providers" },
  { label: "Services", to: "/services" },
  { label: "Share a need", to: "/request" },
] as const;

const ABOUT_LINKS = [
  { label: "About Hami", to: "/about" },
  { label: "How we work", to: "/process" },
  { label: "Hami group", to: "/group" },
  { label: "Businesses", to: "/group/businesses" },
  { label: "Technology", to: "/technology" },
  { label: "Ventures", to: "/ventures" },
  { label: "Contact", to: "/contact" },
] as const;

const LINK =
  "link-arrow w-fit text-sm font-bold text-wheat transition-colors duration-150 hover:text-white";

export function SiteFooter() {
  const year = new Date().getFullYear();
  return (
    <footer className="mt-auto border-t-2 border-white/20 bg-card">
      <div className="band-rule" aria-hidden="true" />
      <Container className="grid gap-10 py-14 sm:grid-cols-2 lg:grid-cols-[1.2fr_1fr_1fr_1.15fr_0.9fr]">
        <div className="sm:col-span-2 lg:col-span-1">
          <p className="font-gothic text-3xl text-accent">
            <span className="font-sans text-2xl font-normal text-wheat" aria-hidden="true">
              ©{" "}
            </span>
            {SITE.name}
          </p>
          <p className="mt-4 max-w-xs text-sm leading-relaxed text-muted">
            Hami is one system. Services are one recorded path through it when public listings and contact routes are available. Nepal is where that path starts.
          </p>
        </div>
        <FooterColumn title="Discover">
          {DISCOVERY_LINKS.map((item) => (
            <Link key={item.to} to={item.to} className={LINK}>
              {item.label}
            </Link>
          ))}
        </FooterColumn>
        <FooterColumn title="Take part">
          {ACTION_LINKS.map((item) => (
            <Link key={item.to} to={item.to} className={LINK}>
              {item.label}
            </Link>
          ))}
        </FooterColumn>
        <FooterColumn title="About">
          {ABOUT_LINKS.map((item) => (
            <Link key={item.to} to={item.to} className={LINK}>
              {item.label}
            </Link>
          ))}
        </FooterColumn>
        <FooterColumn title="Connect">
          {SITE.email ? (
            <a href={`mailto:${SITE.email}`} className={LINK}>
              {SITE.email}
            </a>
          ) : (
            <span className="text-sm text-muted">Contact mailbox pending</span>
          )}
          {SITE.url ? (
            <a href={SITE.url} className={LINK}>
              {SITE.domain}
            </a>
          ) : (
            <span className="text-sm text-muted">{SITE.domain}</span>
          )}
        </FooterColumn>
      </Container>
      <div className="border-t-2 border-white/10 bg-black">
        <Container className="flex flex-col gap-2 py-4 text-micro font-bold uppercase tracking-[0.12em] text-dim sm:flex-row sm:items-center sm:justify-between">
          <span>
            © {year} {SITE.name}
          </span>
          <span>
            {SITE.name} · {SITE.domain}
          </span>
          <span className="text-wheat">{SITE.location}</span>
        </Container>
      </div>
    </footer>
  );
}

function FooterColumn({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="flex flex-col gap-3">
      <h2 className="mb-1 text-base font-extrabold text-accent">{title}</h2>
      {children}
    </div>
  );
}
