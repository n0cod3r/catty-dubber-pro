import { lazy, Suspense, type ComponentProps } from "react";

import { LoaderCircle } from "lucide-react";

const Workspace = lazy(() =>
  import("./editor-workspace").then((module) => ({
    default: module.EditorWorkspace,
  })),
);

export function LazyEditorWorkspace(props: ComponentProps<typeof Workspace>) {
  return (
    <Suspense
      fallback={
        <div
          role="status"
          className="flex min-h-0 flex-1 items-center justify-center gap-2 text-sm text-muted-foreground"
        >
          <LoaderCircle aria-hidden="true" className="size-4 animate-spin" />
          Loading editor…
        </div>
      }
    >
      <Workspace {...props} />
    </Suspense>
  );
}
