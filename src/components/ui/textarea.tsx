import * as React from "react";
import { cn } from "@/lib/utils";

function Textarea({ className, ...props }: React.ComponentProps<"textarea">) {
  return (
    <textarea
      className={cn(
        "min-h-28 w-full resize-y rounded-md border border-line bg-void px-3 py-2.5 text-sm text-fg outline-none transition-[border-color,box-shadow] duration-150 placeholder:text-dim focus-visible:border-cyan focus-visible:shadow-[var(--shadow-glow)] disabled:opacity-50",
        className,
      )}
      {...props}
    />
  );
}

export { Textarea };
