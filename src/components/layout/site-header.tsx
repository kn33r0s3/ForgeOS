import { useEffect, useState } from "react";
import { ArrowUpRight, Menu, X } from "lucide-react";
import { Link, useRouterState } from "@tanstack/react-router";
import { NAV } from "@/lib/content";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { BrandMark } from "./brand-mark";
import { Container } from "./container";

function isActive(href: string, pathname: string) {
  if (href === "/group") return pathname === "/group";
  if (href === "/services") return pathname === "/services" || pathname.startsWith("/services/");
  return pathname === href;
}

export function SiteHeader() {
  const [open, setOpen] = useState(false);
  const pathname = useRouterState({ select: (s) => s.location.pathname });
  const [scrolled, setScrolled] = useState(false);

  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 8);
    onScroll();
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => window.removeEventListener("scroll", onScroll);
  }, []);

  useEffect(() => {
    setOpen(false);
  }, [pathname]);

  useEffect(() => {
    if (!open) return;
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") setOpen(false);
    };
    document.body.style.overflow = "hidden";
    window.addEventListener("keydown", onKey);
    return () => {
      document.body.style.overflow = "";
      window.removeEventListener("keydown", onKey);
    };
  }, [open]);

  // The mobile sheet is a sibling of <header>, not a child: the header's
  // backdrop-filter would otherwise become the containing block for the
  // fixed sheet and clip it to the header's height.
  return (
    <>
      <header
        className={cn(
          "sticky top-0 z-50 h-[var(--header-h)] border-b transition-[background-color,border-color] duration-200",
          scrolled || open
            ? "border-line bg-paper/85 backdrop-blur-xl"
            : "border-transparent bg-paper/60 backdrop-blur-md",
        )}
      >
        <Container className="relative flex h-full items-center justify-between gap-4">
          <BrandMark />
          <nav
            className="hidden items-center gap-1 rounded-full border border-line/80 bg-card/50 p-1 lg:flex"
            aria-label="Main navigation"
          >
            {NAV.map((item) => {
              const active = isActive(item.to, pathname);
              return (
                <Link
                  key={item.to}
                  to={item.to}
                  aria-current={active ? "page" : undefined}
                  className={cn(
                    "relative rounded-full px-4 py-1.5 text-nav transition-colors duration-150",
                    active
                      ? "bg-accent/12 text-accent"
                      : "text-muted hover:bg-secondary hover:text-ink",
                  )}
                >
                  {item.label}
                </Link>
              );
            })}
          </nav>
          <div className="flex items-center gap-2">
            <Button asChild size="sm" className="hidden lg:inline-flex">
              <Link to="/actions">
                Review actions
                <ArrowUpRight />
              </Link>
            </Button>
            <button
              type="button"
              className="inline-flex size-11 items-center justify-center rounded-card border border-line bg-card/60 text-ink transition-colors hover:border-accent/60 lg:hidden"
              aria-expanded={open}
              aria-controls="mobile-navigation"
              aria-label={open ? "Close navigation" : "Open navigation"}
              onClick={() => setOpen((value) => !value)}
            >
              <span className="relative size-5">
                <Menu
                  className={cn(
                    "absolute inset-0 size-5 transition-[opacity,transform,filter] duration-200",
                    open ? "scale-[0.25] opacity-0 blur-[4px]" : "scale-100 opacity-100",
                  )}
                />
                <X
                  className={cn(
                    "absolute inset-0 size-5 transition-[opacity,transform,filter] duration-200",
                    open ? "scale-100 opacity-100" : "scale-[0.25] opacity-0 blur-[4px]",
                  )}
                />
              </span>
            </button>
          </div>
        </Container>
      </header>
      <div
        id="mobile-navigation"
        hidden={!open}
        className={cn(
          "fixed inset-x-0 bottom-0 top-[var(--header-h)] z-40 overflow-y-auto bg-paper/97 backdrop-blur-xl lg:hidden",
          open ? "block" : "hidden",
        )}
      >
        <div className="hero-glow" aria-hidden="true" />
        <Container className="relative flex min-h-full flex-col py-6">
          <nav aria-label="Mobile navigation">
            <ol className="flex flex-col">
              {NAV.map((item, index) => {
                const active = isActive(item.to, pathname);
                return (
                  <li
                    key={item.to}
                    className="reveal border-b border-line"
                    style={{ "--i": index } as React.CSSProperties}
                  >
                    <Link
                      to={item.to}
                      aria-current={active ? "page" : undefined}
                      className={cn(
                        "flex min-h-16 items-center justify-between gap-4 font-display text-3xl tracking-tight transition-colors",
                        active ? "text-accent" : "text-ink hover:text-accent",
                      )}
                    >
                      <span className="flex items-baseline gap-4">
                        <span className="font-mono text-micro tracking-[0.14em] text-dim">
                          {String(index + 1).padStart(2, "0")}
                        </span>
                        {item.label}
                      </span>
                      <ArrowUpRight className="size-5 text-dim" aria-hidden="true" />
                    </Link>
                  </li>
                );
              })}
            </ol>
          </nav>
          <div
            className="reveal mt-8 grid grid-cols-2 gap-2 text-sm"
            style={{ "--i": NAV.length } as React.CSSProperties}
          >
            {SECONDARY.map((item) => (
              <Link
                key={item.to}
                to={item.to}
                className="flex min-h-11 items-center rounded-card border border-line bg-card/60 px-3 text-muted transition-colors hover:border-accent/60 hover:text-ink"
              >
                {item.label}
              </Link>
            ))}
          </div>
          <Button
            asChild
            size="lg"
            className="reveal mt-auto w-full"
            style={{ "--i": NAV.length + 1 } as React.CSSProperties}
          >
            <Link to="/actions">
              Review actions
              <ArrowUpRight />
            </Link>
          </Button>
        </Container>
      </div>
    </>
  );
}

const SECONDARY = [
  { label: "Operations", to: "/operations" },
  { label: "Providers", to: "/providers" },
  { label: "Work board", to: "/domain" },
  { label: "About", to: "/about" },
] as const;
