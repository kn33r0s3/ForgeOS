import * as React from "react";
import { cn } from "@/lib/utils";

function Input({ className, type, ...props }: React.ComponentProps<"input">) {
  return (
    <input
      type={type}
      className={cn(
        "h-11 w-full rounded-md border border-border bg-surface px-3 text-sm text-foreground outline-none transition-[border-color,box-shadow] duration-150 placeholder:text-muted focus-visible:border-focus focus-visible:shadow-[var(--shadow-glow)] disabled:opacity-50",
        className,
      )}
      {...props}
    />
  );
}

export { Input };
