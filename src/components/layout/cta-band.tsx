import type { ReactNode } from "react";
import { ArrowUpRight } from "lucide-react";
import { Link } from "@tanstack/react-router";
import { Button } from "@/components/ui/button";
import { Container } from "./container";
import { Eyebrow } from "./eyebrow";

export function CtaBand({
  eyebrow = "Independent provider directory",
  title = (
    <>
      Find an external provider
      <br />
      <span className="text-muted">when the work needs one.</span>
    </>
  ),
  body = "Hami's service catalogue describes Hami's own technical scope. This separate directory lists providers only when verified and published. A request stays pending until a provider accepts it; browsing does not create a booking.",
  to = "/providers",
  actionLabel = "Browse verified providers",
}: {
  eyebrow?: string;
  title?: ReactNode;
  body?: string;
  to?: "/providers" | "/services" | "/process" | "/group/businesses";
  actionLabel?: string;
}) {
  return (
    <section className="border-t border-line bg-card py-16 sm:py-20">
      <Container className="flex flex-col items-start justify-between gap-8 lg:flex-row lg:items-end">
        <div className="max-w-xl">
          <Eyebrow>{eyebrow}</Eyebrow>
          <h2 className="font-display text-title tracking-tight text-ink">{title}</h2>
          <p className="mt-4 max-w-md text-sm leading-relaxed text-muted">{body}</p>
        </div>
        <Button asChild size="lg">
          <Link to={to}>
            {actionLabel}
            <ArrowUpRight />
          </Link>
        </Button>
      </Container>
    </section>
  );
}
