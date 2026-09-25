import { ArrowUpRight } from "lucide-react";
import { Link } from "@tanstack/react-router";
import { Button } from "@/components/ui/button";
import { Container } from "@/components/layout/container";
import { Eyebrow } from "@/components/layout/eyebrow";

export function NotFoundPage() {
  return (
    <main className="flex flex-1 items-center py-24">
      <Container className="max-w-xl">
        <Eyebrow tone="amber">404</Eyebrow>
        <h1 className="font-display text-display tracking-tight text-fg">
          This page
          <br />
          <span className="text-muted">is not here.</span>
        </h1>
        <p className="mt-6 max-w-md text-lede text-muted">
          The address does not match a public Forge route. Utility tools are not
          part of this platform.
        </p>
        <Button asChild className="mt-8">
          <Link to="/">
            Back to home
            <ArrowUpRight />
          </Link>
        </Button>
      </Container>
    </main>
  );
}
