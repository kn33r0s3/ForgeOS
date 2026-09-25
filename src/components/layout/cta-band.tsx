import type { ReactNode } from "react";
import { ArrowUpRight } from "lucide-react";
import { Link } from "@tanstack/react-router";
import { Button } from "@/components/ui/button";
import { Container } from "./container";
import { Eyebrow } from "./eyebrow";

export function CtaBand({
  eyebrow = "Services, one path through the network",
  title = (
    <>
      Verified services
      <br />
      <span className="text-muted">inside the same network.</span>
    </>
  ),
  body = "A provider appears only after verification and publication. A request stays pending until that provider accepts it. Work, offers, and trades use the same records.",
}: {
  eyebrow?: string;
  title?: ReactNode;
  body?: string;
}) {
  return (
    <section className="border-t border-line bg-raised py-16 sm:py-20">
      <Container className="flex flex-col items-start justify-between gap-8 lg:flex-row lg:items-end">
        <div className="max-w-xl">
          <Eyebrow>{eyebrow}</Eyebrow>
          <h2 className="font-display text-title tracking-tight text-fg">{title}</h2>
          <p className="mt-4 max-w-md text-sm leading-relaxed text-muted">{body}</p>
        </div>
        <Button asChild size="lg">
          <Link to="/providers">
            Find a service
            <ArrowUpRight />
          </Link>
        </Button>
      </Container>
    </section>
  );
}
