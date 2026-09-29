import * as React from "react";
import { Slot } from "@radix-ui/react-slot";
import { cva, type VariantProps } from "class-variance-authority";
import { cn } from "@/lib/utils";

const buttonVariants = cva(
  "inline-flex items-center justify-center gap-2 whitespace-nowrap rounded-card text-sm font-extrabold tracking-tight transition-[transform,background-color,background-position,color,border-color,box-shadow] duration-150 ease-out disabled:pointer-events-none disabled:opacity-50 [&_svg]:pointer-events-none [&_svg]:size-4 [&_svg]:shrink-0 outline-none active:not-disabled:translate-y-px",
  {
    variants: {
      variant: {
        // KneeRose button: orange with a dark edge; a black plate wipes across on hover.
        primary:
          "btn-wipe border-2 border-black/70 bg-accent text-black shadow-sm hover:text-accent",
        // KneeRose second button: off-white with black type.
        secondary:
          "btn-wipe border-2 border-black/70 bg-[#f5f1f1] text-black shadow-sm hover:text-white",
        ghost: "text-wheat underline-offset-4 hover:text-accent hover:underline",
        warning: "btn-wipe border-2 border-black/70 bg-warning text-black shadow-sm hover:text-warning",
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
