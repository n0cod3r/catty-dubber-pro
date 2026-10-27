import { useState, type CSSProperties } from "react";

import { AlertCircle, ChevronLeft, LoaderCircle, X } from "lucide-react";

import { AppSidebar } from "@/components/editor/app-sidebar";
import { EditorErrorBoundary } from "@/components/editor/editor-error-boundary";
import { EditorWorkspace } from "@/components/editor/editor-workspace";
import { WorkspaceHeader } from "@/components/editor/workspace-header";
import { ProjectHome } from "@/components/projects/project-home";
import { Button } from "@/components/ui/button";
import { SidebarProvider } from "@/components/ui/sidebar";
import { TooltipProvider } from "@/components/ui/tooltip";
import { useEpisode } from "@/features/editor/use-episode";
import { useDesktopShutdown } from "@/features/engine/use-desktop-shutdown";
import { useProject } from "@/features/projects/use-project";

export function App() {
  const projects = useProject();
  const source = useEpisode(projects.current?.directory ?? null, projects.current?.project ?? null);
  const closing = useDesktopShutdown();
  const [followPlayhead, setFollowPlayhead] = useState(true);
  const onImport = () => void source.openEpisode();

  if (closing)
    return (
      <div role="status" className="flex h-svh items-center justify-center gap-3 bg-background text-foreground">
        <LoaderCircle className="size-5 animate-spin text-primary" />
        <div>
          <p className="text-sm font-medium">កំពុងបិទ Catty…</p>
          <p className="mt-1 text-xs text-muted-foreground">កំពុងបញ្ឈប់ audio preparation និង background work។</p>
        </div>
      </div>
    );

  if (!projects.current)
    return (
      <ProjectHome
        busy={projects.busy}
        error={projects.error}
        recents={projects.recentProjects}
        onCreate={projects.create}
        onOpen={projects.chooseAndOpen}
        onOpenRecent={projects.openRecent}
      />
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
            <div className="flex h-8 shrink-0 items-center gap-2 border-b bg-card/60 px-2.5">
              <Button variant="ghost" size="icon-xs" aria-label="ត្រឡប់ទៅ Projects" onClick={projects.close}>
                <ChevronLeft />
              </Button>
              <span className="truncate text-xs font-medium">{projects.current.project.name}</span>
              <span className="hidden truncate text-[10px] text-muted-foreground md:block">{projects.current.directory}</span>
              <span className="ml-auto text-[10px] text-muted-foreground">
                {projects.current.project.episodes.length} episodes
              </span>
            </div>
            <WorkspaceHeader episode={source.episode} importing={source.importing} onImport={onImport} />
            {source.error && (
              <div role="alert" className="flex shrink-0 items-center gap-2 border-b border-destructive/30 bg-destructive/10 px-3 py-2 text-xs">
                <AlertCircle className="size-4 shrink-0 text-destructive" />
                <span className="flex-1">{source.error}</span>
                <Button variant="ghost" size="icon-xs" aria-label="បិទសារ error" onClick={source.dismissError}>
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
            aria-label="ជ្រើស episode file"
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
