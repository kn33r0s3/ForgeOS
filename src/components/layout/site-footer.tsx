import { Link } from "@tanstack/react-router";
import { SITE } from "@/lib/content";
import { Container } from "./container";

const GROUP_LINKS = [
  { label: "Hami home", to: "/" },
  { label: "Persisted discoveries", to: "/discoveries" },
  { label: "World stream", to: "/feed" },
  { label: "Opportunity hypotheses", to: "/opportunities" },
  { label: "Action state", to: "/actions" },
  { label: "For businesses", to: "/group/businesses" },
  { label: "Verified providers", to: "/providers" },
  { label: "Public work board", to: "/domain" },
  { label: "About Hami", to: "/about" },
] as const;

const WORK_LINKS = [
  { label: "Edit personal context", to: "/system" },
  { label: "Share a need", to: "/request" },
  { label: "Work board", to: "/domain" },
  { label: "Browse provider records", to: "/providers" },
] as const;

const LINK =
  "link-arrow w-fit text-sm font-bold text-wheat transition-colors duration-150 hover:text-white";

export function SiteFooter() {
  const year = new Date().getFullYear();
  return (
    <footer className="mt-auto border-t-2 border-white/20 bg-card">
      <div className="band-rule" aria-hidden="true" />
      <Container className="grid gap-10 py-14 sm:grid-cols-2 lg:grid-cols-[1.3fr_1fr_1fr_1fr]">
        <div className="sm:col-span-2 lg:col-span-1">
          <p className="font-gothic text-3xl text-accent">
            <span className="font-sans text-2xl font-normal text-wheat" aria-hidden="true">
              ©{" "}
            </span>
            {SITE.name}
          </p>
          <p className="mt-4 max-w-xs text-sm leading-relaxed text-muted">
            Hami is one system. Built in Kathmandu, serving everywhere equally.
          </p>
        </div>
        <FooterColumn title="Explore">
          {GROUP_LINKS.map((item) => (
            <Link key={item.to} to={item.to} className={LINK}>
              {item.label}
            </Link>
          ))}
        </FooterColumn>
        <FooterColumn title="Quick links">
          {WORK_LINKS.map((item) => (
            <Link key={item.to} to={item.to} className={LINK}>
              {item.label}
            </Link>
          ))}
        </FooterColumn>
        <FooterColumn title="Connect">
          <Link to="/feed" className={LINK}>
            Explore the network
          </Link>
          {SITE.email ? (
            <a href={`mailto:${SITE.email}`} className={LINK}>
              {SITE.email}
            </a>
          ) : (
            <span className="text-sm text-muted">Online inquiries are not open yet.</span>
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
