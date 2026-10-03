import { ArrowUpRight } from "lucide-react";
import { Link } from "@tanstack/react-router";
import { Button } from "@/components/ui/button";
import { SITE } from "@/lib/content";

export function ProjectInquiryCta() {
  if (SITE.email) {
    return (
      <Button asChild className="mt-8">
        <Link to="/request">
          Start a Project
          <ArrowUpRight />
        </Link>
      </Button>
    );
  }

  return (
    <div className="mt-8 max-w-md" role="status">
      <p className="text-sm text-muted">Online inquiries are not open yet.</p>
      <div className="mt-3 flex flex-wrap gap-x-5 gap-y-2 text-sm">
        <Link to="/providers" className="text-cyan hover:underline">Browse verified services</Link>
        <Link to="/domain" className="text-cyan hover:underline">Post public work</Link>
      </div>
    </div>
  );
}