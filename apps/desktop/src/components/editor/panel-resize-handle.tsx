import { useRef } from "react";

import { clamp } from "@/features/timeline/geometry";
import { cn } from "@/lib/utils";

type Props = {
  orientation: "horizontal" | "vertical";
  label: string;
  controls: string;
  value: number;
  min: number;
  max: number;
  reset: number;
  onChange: (value: number) => void;
  valueAt: (x: number, y: number) => number;
};

export function PanelResizeHandle({
  orientation,
  label,
  controls,
  value,
  min,
  max,
  reset,
  onChange,
  valueAt,
}: Props) {
  const pointerRef = useRef<number | null>(null);
  const horizontal = orientation === "horizontal";
  return (
    <div
      role="separator"
      tabIndex={0}
      aria-label={label}
      aria-orientation={orientation}
      aria-controls={controls}
      aria-valuemin={Math.round(min)}
      aria-valuemax={Math.round(max)}
      aria-valuenow={Math.round(value)}
      className={cn(
        "group relative z-10 touch-none bg-card outline-none hover:bg-primary/30 focus-visible:bg-primary/40",
        horizontal ? "cursor-row-resize border-y" : "cursor-col-resize border-x",
      )}
      onDoubleClick={() => onChange(clamp(reset, min, max))}
      onKeyDown={(event) => {
        const grow = horizontal ? "ArrowUp" : "ArrowLeft";
        const shrink = horizontal ? "ArrowDown" : "ArrowRight";
        const next =
          event.key === grow
            ? value + 16
            : event.key === shrink
              ? value - 16
              : event.key === "Home"
                ? min
                : event.key === "End"
                  ? max
                  : null;
        if (next !== null) {
          event.preventDefault();
          onChange(clamp(next, min, max));
        }
      }}
      onPointerDown={(event) => {
        if (event.button !== 0) return;
        event.preventDefault();
        event.currentTarget.focus();
        pointerRef.current = event.pointerId;
        event.currentTarget.setPointerCapture(event.pointerId);
      }}
      onPointerMove={(event) => {
        if (pointerRef.current === event.pointerId)
          onChange(clamp(valueAt(event.clientX, event.clientY), min, max));
      }}
      onPointerUp={(event) => {
        pointerRef.current = null;
        if (event.currentTarget.hasPointerCapture(event.pointerId))
          event.currentTarget.releasePointerCapture(event.pointerId);
      }}
      onPointerCancel={() => {
        pointerRef.current = null;
      }}
      onLostPointerCapture={() => {
        pointerRef.current = null;
      }}
    >
      <span
        className={cn(
          "absolute bg-muted-foreground/50",
          horizontal ? "inset-x-0 top-1/2 mx-auto h-px w-8" : "inset-y-0 left-1/2 my-auto h-8 w-px",
        )}
      />
    </div>
  );
}
