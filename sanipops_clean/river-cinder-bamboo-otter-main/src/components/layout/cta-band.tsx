import type { ReactNode } from "react";
import { ArrowUpRight } from "lucide-react";
import { Link } from "@tanstack/react-router";
import { Button } from "@/components/ui/button";
import { Container } from "./container";
import { Eyebrow } from "./eyebrow";

export function CtaBand({
  eyebrow = "A sensible next step",
  title = (
    <>
      Have a hard-to-explain
      <br />
      <span className="text-muted">problem?</span>
    </>
  ),
  body = "Start with the situation. We’ll help work out what the system should be.",
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
          <Link to="/request">
            Start a Project
            <ArrowUpRight />
          </Link>
        </Button>
      </Container>
    </section>
  );
}
