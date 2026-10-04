import { Link } from "@tanstack/react-router";
import { SITE } from "@/lib/content";
import { Container } from "./container";

const SYSTEM_LINKS = [
  { label: "Hami overview", to: "/" },
  { label: "One system", to: "/about" },
  { label: "How Hami works", to: "/process" },
  { label: "Group directions", to: "/group" },
] as const;

const RECORD_LINKS = [
  { label: "Published observations", to: "/discoveries" },
  { label: "Open questions", to: "/unknowns" },
  { label: "Opportunity hypotheses", to: "/opportunities" },
  { label: "Public network records", to: "/feed" },
] as const;

const WORK_LINKS = [
  { label: "Experiment 1", to: "/needs" },
  { label: "Public work board", to: "/domain" },
  { label: "Verified services", to: "/providers" },
  { label: "Hami services", to: "/services" },
  { label: "Contact", to: "/contact" },
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
        <FooterColumn title="The system">
          {SYSTEM_LINKS.map((item) => (
            <Link key={item.to} to={item.to} className={LINK}>
              {item.label}
            </Link>
          ))}
        </FooterColumn>
        <FooterColumn title="Public record">
          {RECORD_LINKS.map((item) => (
            <Link key={item.to} to={item.to} className={LINK}>
              {item.label}
            </Link>
          ))}
        </FooterColumn>
        <FooterColumn title="Work & contact">
          {WORK_LINKS.map((item) => (
            <Link key={item.to} to={item.to} className={LINK}>
              {item.label}
            </Link>
          ))}
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
