import type { ReactNode } from "react";
import { ArrowUpRight } from "lucide-react";
import { Link } from "@tanstack/react-router";
import { cn } from "@/lib/utils";

export type TextLinkTo =
  | "/"
  | "/services"
  | "/group"
  | "/group/businesses"
  | "/about"
  | "/contact"
  | "/request"
  | "/process";

export function TextLink({
  to,
  children,
  className,
  onClick,
}: {
  to: TextLinkTo;
  children: ReactNode;
  className?: string;
  onClick?: () => void;
}) {
  return (
    <Link
      to={to}
      onClick={onClick}
      className={cn(
        "inline-flex items-center gap-1.5 text-nav font-semibold text-accent transition-colors duration-150 hover:text-ink",
        className,
      )}
    >
      {children}
      <ArrowUpRight className="size-3.5" />
    </Link>
  );
}
