import { useState, type CSSProperties } from "react";

import { AlertCircle, LoaderCircle, X } from "lucide-react";

import { AppSidebar } from "@/components/editor/app-sidebar";
import { EditorErrorBoundary } from "@/components/editor/editor-error-boundary";
import { EditorWorkspace } from "@/components/editor/editor-workspace";
import { WorkspaceHeader } from "@/components/editor/workspace-header";
import { Button } from "@/components/ui/button";
import { SidebarProvider } from "@/components/ui/sidebar";
import { TooltipProvider } from "@/components/ui/tooltip";
import { useEpisode } from "@/features/editor/use-episode";
import { useDesktopShutdown } from "@/features/engine/use-desktop-shutdown";

export function App() {
  const source = useEpisode();
  const closing = useDesktopShutdown();
  const [followPlayhead, setFollowPlayhead] = useState(true);
  const onImport = () => {
    void source.openEpisode();
  };

  if (closing)
    return (
      <div
        role="status"
        className="flex h-svh items-center justify-center gap-3 bg-background text-foreground"
      >
        <LoaderCircle className="size-5 animate-spin text-primary" />
        <div>
          <p className="text-sm font-medium">Closing Catty…</p>
          <p className="mt-1 text-xs text-muted-foreground">
            Stopping audio preparation and background work.
          </p>
        </div>
      </div>
    );

  return (
    <EditorErrorBoundary>
      <TooltipProvider>
        <SidebarProvider
          className="h-svh min-h-0 overflow-hidden bg-background text-foreground"
          style={{ "--sidebar-width": "14rem" } as CSSProperties}
          defaultOpen={false}
        >
          <AppSidebar
            episode={source.episode}
            importing={source.importing}
            onImport={onImport}
            followPlayhead={followPlayhead}
            onFollowChange={setFollowPlayhead}
          />
          <main className="flex min-h-0 min-w-0 flex-1 flex-col overflow-hidden">
            <WorkspaceHeader
              episode={source.episode}
              importing={source.importing}
              onImport={onImport}
            />
            {source.error && (
              <div
                role="alert"
                className="flex shrink-0 items-center gap-2 border-b border-destructive/30 bg-destructive/10 px-3 py-2 text-xs"
              >
                <AlertCircle className="size-4 shrink-0 text-destructive" />
                <span className="flex-1">{source.error}</span>
                <Button
                  variant="ghost"
                  size="icon-xs"
                  aria-label="Dismiss import error"
                  onClick={source.dismissError}
                >
                  <X />
                </Button>
              </div>
            )}
            <EditorWorkspace
              key={source.episode?.id ?? "empty"}
              episode={source.episode}
              importing={source.importing}
              onImport={onImport}
              onMetadata={source.updateMetadata}
              followPlayhead={followPlayhead}
            />
          </main>
          <input
            ref={source.fileInputRef}
            type="file"
            className="hidden"
            aria-label="Choose episode file"
            accept=".mp4,.mov,.mkv,.webm,.m4v,.avi"
            onChange={(event) => {
              const file = event.currentTarget.files?.[0];
              if (file) source.importFile(file);
              event.currentTarget.value = "";
            }}
          />
        </SidebarProvider>
      </TooltipProvider>
    </EditorErrorBoundary>
  );
}
