import { clsx, type ClassValue } from "clsx";
import { extendTailwindMerge } from "tailwind-merge";

/**
 * tailwind-merge only knows Tailwind's default font-size scale, so custom
 * `@theme` sizes (`text-micro`, `text-nav`, …) were treated as text colours
 * and silently dropped whenever a colour class followed them. Register the
 * design-system sizes so `cn()` keeps both size and colour.
 */
const twMerge = extendTailwindMerge({
  extend: {
    theme: {
      text: ["display", "title", "lede", "nav", "micro", "kicker"],
    },
  },
});

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}
