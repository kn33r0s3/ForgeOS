import * as React from "react";
import { Slot } from "@radix-ui/react-slot";
import { cva, type VariantProps } from "class-variance-authority";
import { cn } from "@/lib/utils";

const buttonVariants = cva(
  "inline-flex items-center justify-center gap-2 whitespace-nowrap rounded-card text-nav font-semibold tracking-tight transition-[transform,background-color,color,border-color,box-shadow] duration-150 ease-out disabled:pointer-events-none disabled:opacity-50 [&_svg]:pointer-events-none [&_svg]:size-4 [&_svg]:shrink-0 outline-none focus-visible:ring-2 focus-visible:ring-focus/70 focus-visible:ring-offset-2 focus-visible:ring-offset-background active:not-disabled:scale-[0.98]",
  {
    variants: {
      variant: {
        primary:
          "border border-accent bg-accent text-accent-ink hover:bg-accent/90",
        secondary:
          "border border-line bg-card text-ink hover:border-accent/60 hover:bg-secondary",
        ghost: "text-muted hover:bg-secondary hover:text-accent",
        warning: "bg-warning text-accent-ink hover:bg-warning/90",
      },
      size: {
        default: "h-11 px-4",
        lg: "h-12 px-5",
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
