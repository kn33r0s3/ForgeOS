import { useEffect, useState } from "react";
import { ArrowUpRight } from "lucide-react";
import { Link, useRouterState } from "@tanstack/react-router";
import { NAV } from "@/lib/content";
import { cn } from "@/lib/utils";
import { UserButton } from "@/lib/auth/gates";
import { useCurrentUserState } from "@/lib/auth/use-current-user";
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
  const { user, isPending } = useCurrentUserState();
  // Dev fallback is not a real sign-in: those visitors still see the CTA.
  const signedIn = !!user && !user.isDevFallback;

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
        style={{
          background: "linear-gradient(180deg, #1C1813 0%, #0C0B0A 100%)",
          borderBottom: "2px solid #F2A33A",
        }}
      >
        <Container className="relative flex h-full items-stretch justify-between gap-4">
          <BrandMark tone="light" className="self-center" />
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
            {isPending ? (
              <span
                role="status"
                aria-label="Checking account"
                className="h-9 w-16 animate-pulse rounded-card bg-black/10"
              />
            ) : signedIn ? (
              <UserButton />
            ) : (
              <Link
                to="/login"
                className="hidden min-h-12 items-center rounded-card border-2 px-4 text-sm font-extrabold transition-colors sm:inline-flex"
                style={{
                  borderColor: "#F2A33A",
                  background: "#F2A33A",
                  color: "#0C0B0A",
                }}
              >
                Join Hami
              </Link>
            )}
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
                    "block h-[3px] w-[26px] transition-transform duration-200 ease-[var(--ease-snap)]",
                    open && bar === 0 && "translate-y-2 rotate-45",
                    open && bar === 1 && "scale-x-0",
                    open && bar === 2 && "-translate-y-2 -rotate-45",
                  )}
                  style={{ background: "#F2A33A" }}
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
          {!signedIn && (
            <div className="p-4 sm:hidden">
              <Link
                to="/login"
                onClick={() => setOpen(false)}
                className="flex min-h-12 items-center justify-center rounded-card border-2 px-4 text-base font-extrabold transition-colors"
                style={{
                  borderColor: "#F2A33A",
                  background: "#F2A33A",
                  color: "#0C0B0A",
                }}
              >
                Join Hami
              </Link>
            </div>
          )}
        </div>
      </div>
    </>
  );
}

const ROMAN = ["I", "II", "III", "IV", "V", "VI", "VII", "VIII"];
