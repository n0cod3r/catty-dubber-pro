import type { HTMLAttributes } from "react";

import { cn } from "../../lib/cn";

type BadgeProps = HTMLAttributes<HTMLSpanElement> & {
  tone?: "neutral" | "accent" | "success";
};

export function Badge({ className, tone = "neutral", ...props }: BadgeProps) {
  return (
    <span
      className={cn(
        "inline-flex h-5 items-center rounded-catty border px-1.5 text-[9px] font-medium",
        tone === "neutral" && "border-catty-border bg-catty-panel text-catty-muted",
        tone === "accent" && "border-catty-accent/30 bg-catty-accent-soft text-catty-accent-text",
        tone === "success" && "border-catty-success/30 bg-catty-success/10 text-catty-success-text",
        className,
      )}
      {...props}
    />
  );
}
