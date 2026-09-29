import * as React from "react";
import { cn } from "@/lib/utils";

function Label({ className, ...props }: React.ComponentProps<"label">) {
  return (
    <label
      className={cn("mb-2 block text-xs font-semibold tracking-tight text-ink", className)}
      {...props}
    />
  );
}

export { Label };
