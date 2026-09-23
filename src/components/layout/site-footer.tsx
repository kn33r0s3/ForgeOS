import { Link } from "@tanstack/react-router";
import { SITE } from "@/lib/content";
import { BrandMark } from "./brand-mark";
import { Container } from "./container";
import { Eyebrow } from "./eyebrow";

const GROUP_LINKS = [
  { label: "Group overview", to: "/group" },
  { label: "Businesses", to: "/group/businesses" },
  { label: "Technology", to: "/technology" },
  { label: "Operations", to: "/operations" },
  { label: "Ventures", to: "/ventures" },
] as const;

const WORK_LINKS = [
  { label: "Services", to: "/services" },
  { label: "How we work", to: "/process" },
  { label: "About", to: "/about" },
] as const;

export function SiteFooter() {
  const year = new Date().getFullYear();
  return (
    <footer className="mt-auto border-t border-line bg-raised">
      <Container className="grid gap-10 py-16 sm:grid-cols-2 lg:grid-cols-4">
        <div className="sm:col-span-2 lg:col-span-1">
          <BrandMark />
          <p className="mt-4 max-w-xs text-sm leading-relaxed text-muted">
            A parent business group building, owning, and operating useful systems
            and infrastructure from Nepal.
          </p>
        </div>
        <div className="flex flex-col gap-3">
          <Eyebrow className="mb-1" tone="muted">
            The group
          </Eyebrow>
          {GROUP_LINKS.map((item) => (
            <Link
              key={item.to}
              to={item.to}
              className="text-sm text-muted transition-colors duration-150 hover:text-cyan"
            >
              {item.label}
            </Link>
          ))}
        </div>
        <div className="flex flex-col gap-3">
          <Eyebrow className="mb-1" tone="muted">
            Work
          </Eyebrow>
          {WORK_LINKS.map((item) => (
            <Link
              key={item.to}
              to={item.to}
              className="text-sm text-muted transition-colors duration-150 hover:text-cyan"
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
            to="/request"
            className="text-sm text-muted transition-colors duration-150 hover:text-cyan"
          >
            Start a project
          </Link>
          <a
            href={`mailto:${SITE.email}`}
            className="text-sm text-muted transition-colors duration-150 hover:text-cyan"
          >
            {SITE.email}
          </a>
          <a
            href={SITE.url}
            className="text-sm text-muted transition-colors duration-150 hover:text-cyan"
          >
            {SITE.domain}
          </a>
        </div>
      </Container>
      <Container className="flex flex-col gap-2 border-t border-line py-5 font-mono text-micro uppercase tracking-[0.12em] text-dim sm:flex-row sm:items-center sm:justify-between">
        <span>
          © {year} {SITE.legalName}
        </span>
        <span>
          {SITE.name} · {SITE.domain}
        </span>
        <span>{SITE.location}</span>
      </Container>
    </footer>
  );
}
