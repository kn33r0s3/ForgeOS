import * as React from "react";
import { Slot } from "@radix-ui/react-slot";
import { cva, type VariantProps } from "class-variance-authority";
import { cn } from "@/lib/utils";

const buttonVariants = cva(
  "inline-flex items-center justify-center gap-2 whitespace-nowrap rounded-card text-sm font-extrabold tracking-tight disabled:pointer-events-none disabled:opacity-50 [&_svg]:pointer-events-none [&_svg]:size-4 [&_svg]:shrink-0 outline-none active:not-disabled:translate-y-px",
  {
    variants: {
      variant: {
        // KneeRose button: orange with a dark edge; a black plate wipes across on hover.
        primary:
          "btn-wipe btn-primary border-2 border-black/70 bg-accent text-black hover:text-accent focus-visible:text-accent hover:-translate-y-0.5 focus-visible:-translate-y-0.5 hover:shadow-[0_6px_0_#000] focus-visible:shadow-[0_6px_0_#000]",
        // Light secondary actions use a traveling orange highlight, not the primary wipe.
        secondary:
          "btn-secondary border-2 border-black/70 bg-[#f5f1f1] text-black hover:border-accent focus-visible:border-accent hover:-translate-y-px focus-visible:-translate-y-px hover:shadow-[0_4px_0_#000] focus-visible:shadow-[0_4px_0_#000]",
        ghost: "btn-ghost text-wheat underline-offset-4 hover:text-accent focus-visible:text-accent",
        warning:
          "btn-warning border-2 border-black/70 bg-warning text-black hover:border-black focus-visible:border-black hover:-translate-y-px focus-visible:-translate-y-px hover:shadow-[inset_5px_0_0_#000,0_4px_0_#000] focus-visible:shadow-[inset_5px_0_0_#000,0_4px_0_#000]",
      },
      size: {
        default: "h-11 px-4",
        lg: "h-12 px-5 text-base",
        sm: "h-9 px-3 text-micro",
      },
    },
    defaultVariants: {
      variant: "primary",
      size: "default",
    },
  },
);

function Button({
  className,
  variant,
  size,
  asChild = false,
  ...props
}: React.ComponentProps<"button"> &
  VariantProps<typeof buttonVariants> & {
    asChild?: boolean;
  }) {
  const Comp = asChild ? Slot : "button";
  return <Comp className={cn(buttonVariants({ variant, size, className }))} {...props} />;
}

export { Button, buttonVariants };
