import { useState } from "react";

import {
  AudioLines,
  Clapperboard,
  Film,
  FolderOpen,
  Keyboard,
  Library,
  Settings2,
  Upload,
  Volume2,
} from "lucide-react";

import { Button } from "@/components/ui/button";
import {
  Sidebar,
  SidebarContent,
  SidebarFooter,
  SidebarGroup,
  SidebarGroupLabel,
  SidebarHeader,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
  SidebarRail,
  useSidebar,
} from "@/components/ui/sidebar";
import type { EpisodeMedia } from "@/features/editor/deps/episodes";
import { formatTime } from "@/shared/utils/time";

const sections = [
  { id: "project", label: "Project", icon: Clapperboard },
  { id: "media", label: "Episodes", icon: Library },
  { id: "voices", label: "Voice library", icon: AudioLines },
  { id: "settings", label: "Editor settings", icon: Settings2 },
] as const;
type Section = (typeof sections)[number]["id"];

type AppSidebarProps = {
  episode: EpisodeMedia | null;
  importing: boolean;
  onImport: () => void;
  followPlayhead: boolean;
  onFollowChange: (value: boolean) => void;
};

export function AppSidebar({
  episode,
  importing,
  onImport,
  followPlayhead,
  onFollowChange,
}: AppSidebarProps) {
  const [section, setSection] = useState<Section>("project");
  const { setOpen, isMobile, setOpenMobile } = useSidebar();

  function selectSection(next: Section) {
    setSection(next);
    if (isMobile) setOpenMobile(true);
    else setOpen(true);
  }

  return (
    <Sidebar collapsible="icon" className="border-r border-sidebar-border">
      <SidebarHeader className="h-12 justify-center border-b border-sidebar-border px-3 group-data-[collapsible=icon]:px-2">
        <div className="flex items-center gap-2.5 overflow-hidden">
          <div className="grid size-8 shrink-0 place-items-center rounded-lg bg-primary text-primary-foreground">
            <Clapperboard className="size-4" />
          </div>
          <div className="min-w-0 group-data-[collapsible=icon]:hidden">
            <p className="text-sm font-semibold tracking-tight">
              Catty{" "}
              <span className="font-normal text-muted-foreground">
                Dubber Pro
              </span>
            </p>
            <p className="text-[9px] uppercase tracking-[0.16em] text-muted-foreground">
              Dubbing studio
            </p>
          </div>
        </div>
      </SidebarHeader>
      <SidebarContent>
        <SidebarGroup>
          <SidebarGroupLabel>Workspace</SidebarGroupLabel>
          <SidebarMenu>
            {sections.map(({ id, label, icon: Icon }) => (
              <SidebarMenuItem key={id}>
                <SidebarMenuButton
                  isActive={section === id}
                  aria-current={section === id ? "page" : undefined}
                  tooltip={label}
                  onClick={() => selectSection(id)}
                  className="text-xs"
                >
                  <Icon />
                  <span>{label}</span>
                </SidebarMenuButton>
              </SidebarMenuItem>
            ))}
          </SidebarMenu>
        </SidebarGroup>
        <SidebarGroup className="flex-1 border-t border-sidebar-border group-data-[collapsible=icon]:hidden">
          <SidebarGroupLabel>
            {sections.find((item) => item.id === section)?.label}
          </SidebarGroupLabel>
          <div className="space-y-4 px-2 py-1 text-xs">
            {(section === "project" || section === "media") && (
              <>
                {episode ? (
                  <div className="overflow-hidden rounded-lg border bg-background/50">
                    <div className="grid h-24 place-items-center border-b bg-gradient-to-br from-primary/15 to-muted">
                      <Film className="size-8 text-primary/70" />
                    </div>
                    <div className="space-y-2 p-3">
                      <p className="truncate font-medium" title={episode.name}>
                        {episode.name}
                      </p>
                      <div className="flex flex-wrap gap-2 text-[10px] text-muted-foreground">
                        <span className="uppercase">{episode.extension}</span>
                        <span>
                          {episode.durationSeconds
                            ? formatTime(episode.durationSeconds)
                            : "Reading media…"}
                        </span>
                        {episode.width && episode.height ? (
                          <span>
                            {episode.width} × {episode.height}
                          </span>
                        ) : null}
                      </div>
                    </div>
                  </div>
                ) : (
                  <div className="rounded-lg border border-dashed px-3 py-6 text-center">
                    <FolderOpen className="mx-auto mb-3 size-6 text-muted-foreground" />
                    <p>No episode imported</p>
                    <p className="mt-1 text-[11px] leading-relaxed text-muted-foreground">
                      Start with a video to build your dubbing timeline.
                    </p>
                  </div>
                )}
                <Button
                  variant="outline"
                  size="sm"
                  className="w-full"
                  onClick={onImport}
                  disabled={importing}
                >
                  <Upload />
                  {episode ? "Replace episode" : "Import episode"}
                </Button>
                {section === "project" && (
                  <dl className="space-y-3 text-[11px]">
                    <div className="flex justify-between">
                      <dt className="text-muted-foreground">Target language</dt>
                      <dd>Khmer</dd>
                    </div>
                    <div className="flex justify-between">
                      <dt className="text-muted-foreground">Episodes</dt>
                      <dd>{episode ? 1 : 0}</dd>
                    </div>
                    <div className="flex justify-between">
                      <dt className="text-muted-foreground">Storage</dt>
                      <dd>Current session</dd>
                    </div>
                  </dl>
                )}
              </>
            )}
            {section === "voices" && (
              <div className="rounded-lg border border-dashed px-3 py-6 text-center">
                <Volume2 className="mx-auto mb-3 size-6 text-muted-foreground" />
                <p>No voices assigned</p>
                <p className="mt-2 text-[11px] leading-relaxed text-muted-foreground">
                  Speaker assignments and Khmer voices will appear here when the
                  dubbing engine is connected.
                </p>
              </div>
            )}
            {section === "settings" && (
              <>
                <label className="flex cursor-pointer items-start gap-2 rounded-lg border p-3">
                  <input
                    type="checkbox"
                    className="mt-0.5 accent-primary"
                    checked={followPlayhead}
                    onChange={(event) => onFollowChange(event.target.checked)}
                  />
                  <span>
                    Follow playhead
                    <span className="mt-1 block text-[10px] leading-relaxed text-muted-foreground">
                      Scroll the timeline to keep playback in view.
                    </span>
                  </span>
                </label>
                <div className="space-y-3 rounded-lg border p-3">
                  <p className="flex items-center gap-2 font-medium">
                    <Keyboard className="size-3.5" /> Shortcuts
                  </p>
                  {[
                    ["Play / pause", "Space"],
                    ["Seek 1/30 second", "← / →"],
                    ["Seek five seconds", "Shift + ← / →"],
                    ["Toggle sidebar", "⌘ / Ctrl + B"],
                  ].map(([label, key]) => (
                    <div key={label} className="space-y-1 text-[10px]">
                      <p className="text-muted-foreground">{label}</p>
                      <kbd>{key}</kbd>
                    </div>
                  ))}
                </div>
              </>
            )}
          </div>
        </SidebarGroup>
      </SidebarContent>
      <SidebarFooter className="border-t border-sidebar-border group-data-[collapsible=icon]:hidden">
        <div className="flex items-center gap-2 px-2 py-1 text-[10px] text-muted-foreground">
          <span className="size-1.5 rounded-full bg-emerald-500" />
          Local workspace · Khmer dubbing
        </div>
      </SidebarFooter>
      <SidebarRail />
    </Sidebar>
  );
}
