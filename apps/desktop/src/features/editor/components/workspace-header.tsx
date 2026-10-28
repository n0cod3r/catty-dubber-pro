import { FolderOpen, LoaderCircle } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { SidebarTrigger } from "@/components/ui/sidebar";
import { EngineConnection } from "@/features/editor/deps/engine";
import type { EpisodeMedia } from "@/features/editor/deps/episodes";

import { ImportedCat } from "./imported-cat";

export function WorkspaceHeader({
  episode,
  importing,
  onImport,
}: {
  episode: EpisodeMedia | null;
  importing: boolean;
  onImport: () => void;
}) {
  return (
    <header className="relative flex h-12 shrink-0 items-center gap-3 border-b bg-card px-3">
      <SidebarTrigger />
      <div className="h-5 w-px bg-border" />
      <div className="min-w-0 flex-1">
        <div className="flex items-center gap-2">
          <h1 className="truncate text-xs font-semibold">
            {episode?.name ?? "Untitled project"}
          </h1>
          <Badge variant="outline">{episode ? "Imported" : "Draft"}</Badge>
          {episode && (
            <span className="w-16 shrink-0" aria-hidden="true">
              <ImportedCat />
            </span>
          )}
        </div>
        <p className="mt-0.5 text-[10px] text-muted-foreground">
          Dubbing workspace <span className="px-1">/</span> Source → Khmer
        </p>
      </div>
      <EngineConnection />
      <span className="hidden text-[10px] text-muted-foreground lg:block">
        Session changes · not saved
      </span>
      <Button size="sm" disabled={importing} onClick={onImport}>
        {importing ? <LoaderCircle className="animate-spin" /> : <FolderOpen />}
        {importing
          ? "Opening…"
          : episode
            ? "Replace episode"
            : "Import episode"}
      </Button>
    </header>
  );
}
