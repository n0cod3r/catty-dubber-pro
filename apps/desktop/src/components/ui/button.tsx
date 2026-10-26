import { cva, type VariantProps } from "class-variance-authority";
import type { ButtonHTMLAttributes } from "react";

import { cn } from "../../lib/cn";

const buttonVariants = cva(
  "inline-flex shrink-0 items-center justify-center gap-1.5 whitespace-nowrap rounded-catty border text-[11px] font-medium outline-none transition-colors focus-visible:ring-2 focus-visible:ring-catty-accent/35 disabled:pointer-events-none disabled:opacity-45",
  {
    variants: {
      variant: {
        primary:
          "border-catty-accent-hover bg-catty-accent text-[#17100c] hover:bg-catty-accent-hover",
        secondary:
          "border-catty-border bg-catty-surface text-catty-text hover:border-catty-border-strong hover:bg-catty-surface-hover",
        ghost:
          "border-transparent bg-transparent text-catty-muted hover:bg-catty-surface hover:text-catty-text",
        danger:
          "border-catty-danger/45 bg-catty-danger-soft text-catty-danger-text hover:bg-catty-danger/20",
      },
      size: {
        sm: "h-7 px-2",
        md: "h-8 px-2.5",
        icon: "size-7 p-0",
      },
    },
    defaultVariants: {
      variant: "secondary",
      size: "md",
    },
  },
);

type ButtonProps = ButtonHTMLAttributes<HTMLButtonElement> & VariantProps<typeof buttonVariants>;

export function Button({ className, variant, size, type = "button", ...props }: ButtonProps) {
  return <button className={cn(buttonVariants({ variant, size }), className)} type={type} {...props} />;
}
