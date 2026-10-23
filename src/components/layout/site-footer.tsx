import { Link, useLoaderData } from "@tanstack/react-router";
import { SITE } from "@/lib/content";
import { FOOTER_GROUPS } from "@/lib/hami-system";
import { authEnabled } from "@/lib/auth/client";
import { BrandMark } from "./brand-mark";
import { Container } from "./container";

const LINK =
  "link-arrow w-fit text-sm font-bold text-wheat transition-colors duration-150 hover:text-white";

export function SiteFooter() {
  const year = new Date().getFullYear();
  // Same gate as the header and the login page: never link to sign-in
  // while auth is disabled or unconfigured (see the root loader).
  const { authConfigured } = useLoaderData({ from: "__root__" });
  const authAvailable = authEnabled && authConfigured;
  return (
    <footer
      className="mt-auto"
      style={{ borderTop: "1px solid #3A2E1A", background: "#15130F" }}
    >
      <div className="band-rule" aria-hidden="true" />
      <Container className="grid gap-10 py-14 sm:grid-cols-2 lg:grid-cols-[1.2fr_1fr_1.1fr_1.1fr_1fr]">
        <div className="sm:col-span-2 lg:col-span-1">
          <BrandMark tone="light" />
          <p className="mt-4 max-w-xs text-sm leading-relaxed text-muted">
            Hami is one system. Built in Kathmandu, serving everywhere equally.
          </p>
        </div>
        {FOOTER_GROUPS.map((group) => (
          <FooterColumn key={group.title} title={group.title}>
            {group.items
              .filter((item) => authAvailable || item.to !== "/login")
              .map((item) => (
                <Link key={item.to} to={item.to} className={LINK}>
                  {item.label}
                </Link>
              ))}
          </FooterColumn>
        ))}
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
