import { useEffect, useState } from "react";
import { ArrowUpRight } from "lucide-react";
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

  // The mobile panel is a sibling of <header>, not a child, so it is never
  // clipped by the header's own box.
  return (
    <>
      <header
        className={cn(
          "masthead sticky top-0 z-50 h-[var(--header-h)] transition-shadow duration-150",
          scrolled || open ? "shadow-[0_4px_0_0_#000]" : "",
        )}
      >
        <Container className="relative flex h-full items-stretch justify-between gap-4">
          <BrandMark tone="dark" className="self-center" />
          <nav className="hidden h-full items-stretch lg:flex" aria-label="Main navigation">
            {NAV.map((item) => {
              const active = isActive(item.to, pathname);
              return (
                <Link
                  key={item.to}
                  to={item.to}
                  aria-current={active ? "page" : undefined}
                  className="mast-link text-nav"
                >
                  {item.label}
                </Link>
              );
            })}
          </nav>
          <div className="flex items-center gap-2">
            <Link
              to="/system"
              className="btn-wipe hidden h-10 items-center gap-1.5 rounded-card border-2 border-black bg-black px-4 text-sm font-extrabold text-accent hover:text-wheat lg:inline-flex"
              style={{ backgroundImage: "linear-gradient(45deg, #161515 50%, transparent 50%)" }}
            >
              My gear
              <ArrowUpRight className="size-4" aria-hidden="true" />
            </Link>
            <button
              type="button"
              className="group relative inline-flex size-11 flex-col items-center justify-center gap-[5px] rounded-card lg:hidden"
              aria-expanded={open}
              aria-controls="mobile-navigation"
              aria-label={open ? "Close navigation" : "Open navigation"}
              onClick={() => setOpen((value) => !value)}
            >
              {[0, 1, 2].map((bar) => (
                <span
                  key={bar}
                  aria-hidden="true"
                  className={cn(
                    "block h-[3px] w-[26px] bg-black transition-transform duration-200 ease-[var(--ease-snap)]",
                    open && bar === 0 && "translate-y-2 rotate-45",
                    open && bar === 1 && "scale-x-0",
                    open && bar === 2 && "-translate-y-2 -rotate-45",
                  )}
                />
              ))}
            </button>
          </div>
        </Container>
      </header>
      <div
        id="mobile-navigation"
        hidden={!open}
        className={cn(
          "fixed inset-x-0 bottom-0 top-[var(--header-h)] z-40 overflow-y-auto bg-black/70 lg:hidden",
          open ? "block" : "hidden",
        )}
        onClick={(event) => {
          if (event.target === event.currentTarget) setOpen(false);
        }}
      >
        <div className="reveal mx-2 mt-2 rounded-card border-2 border-line-strong bg-card shadow-md">
          <nav aria-label="Mobile navigation">
            <ol className="flex flex-col">
              {NAV.map((item, index) => {
                const active = isActive(item.to, pathname);
                return (
                  <li
                    key={item.to}
                    className="reveal border-b-2 border-line last:border-b-0"
                    style={{ "--i": index + 1 } as React.CSSProperties}
                  >
                    <Link
                      to={item.to}
                      aria-current={active ? "page" : undefined}
                      className={cn(
                        "flex min-h-14 items-center gap-4 px-4 text-lg font-extrabold transition-colors",
                        active
                          ? "bg-black text-accent"
                          : "text-wheat hover:bg-secondary hover:text-white",
                      )}
                    >
                      <span className="gothic-num w-8 text-right text-xl" aria-hidden="true">
                        {ROMAN[index]}
                      </span>
                      {item.label}
                      <ArrowUpRight className="ml-auto size-5 text-dim" aria-hidden="true" />
                    </Link>
                  </li>
                );
              })}
            </ol>
          </nav>
          <div
            className="reveal grid grid-cols-2 gap-2 border-t-2 border-line p-3 text-sm"
            style={{ "--i": NAV.length + 1 } as React.CSSProperties}
          >
            {SECONDARY.map((item) => (
              <Link
                key={item.to}
                to={item.to}
                className="flex min-h-11 items-center rounded-card border-2 border-line bg-black px-3 font-bold text-wheat transition-colors hover:border-accent hover:text-white"
              >
                {item.label}
              </Link>
            ))}
          </div>
          <div className="reveal p-3 pt-0" style={{ "--i": NAV.length + 2 } as React.CSSProperties}>
            <Button asChild size="lg" className="w-full">
              <Link to="/system">
                My gear
                <ArrowUpRight />
              </Link>
            </Button>
          </div>
        </div>
      </div>
    </>
  );
}

const ROMAN = ["I", "II", "III", "IV", "V", "VI", "VII", "VIII"];

const SECONDARY = [
  { label: "Share a need", to: "/request" },
  { label: "Work board", to: "/domain" },
  { label: "About", to: "/about" },
] as const;
