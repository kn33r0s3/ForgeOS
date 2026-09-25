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

  return (
    <header className="sticky top-0 z-50 h-[var(--header-h)] border-b border-line bg-void/75 backdrop-blur-xl">
      <Container className="relative flex h-full items-center justify-between gap-4">
        <BrandMark />
        <nav
          className="hidden items-center gap-6 xl:flex"
          aria-label="Main navigation"
        >
          {NAV.map((item) => (
            <Link
              key={item.to}
              to={item.to}
              aria-current={isActive(item.to, pathname) ? "page" : undefined}
              className={cn(
                "relative py-2 text-nav text-muted transition-colors duration-150 hover:text-fg",
                isActive(item.to, pathname) && "nav-active",
              )}
            >
              {item.label}
            </Link>
          ))}
        </nav>
        <div className="flex items-center gap-2">
          <Button asChild size="sm" className="hidden sm:inline-flex">
            <Link to="/feed">
              Explore network
              <ArrowUpRight />
            </Link>
          </Button>
          <button
            type="button"
            className="inline-flex size-11 items-center justify-center rounded-md text-fg xl:hidden"
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
      <div
        id="mobile-navigation"
        hidden={!open}
        className={cn(
          "absolute inset-x-0 top-[var(--header-h)] z-40 border-b border-line bg-void/95 backdrop-blur-xl xl:hidden",
          open ? "block" : "hidden",
        )}
      >
        <Container className="flex max-h-[calc(100dvh-var(--header-h))] flex-col gap-1 overflow-y-auto py-4">
          {NAV.map((item) => (
            <Link
              key={item.to}
              to={item.to}
              aria-current={isActive(item.to, pathname) ? "page" : undefined}
              className={cn(
                "flex min-h-11 items-center border-b border-line text-base text-muted last:border-b-0",
                isActive(item.to, pathname) && "text-cyan",
              )}
            >
              {item.label}
            </Link>
          ))}
          <Button asChild className="mt-3 w-full sm:hidden">
            <Link to="/feed">
              Explore network
              <ArrowUpRight />
            </Link>
          </Button>
        </Container>
      </div>
    </header>
  );
}
