import { useRef, useState } from "react";

import { FolderOpen, Library, Mic2, Settings, Sparkles, WandSparkles } from "lucide-react";

import { Badge } from "../components/ui/badge";
import { Button } from "../components/ui/button";
import { DialoguePanel } from "../components/workspace/dialogue-panel";
import { Timeline } from "../components/workspace/timeline";
import { VideoPreview } from "../components/workspace/video-preview";
import { importEpisode } from "../features/episodes/import-episode";
import type { EpisodeMedia } from "../features/episodes/types";
import { usePlayback } from "../features/playback/use-playback";
import { cn } from "../lib/cn";

const workflow = ["Import", "Transcribe", "Translate", "Speakers", "Voices", "Mix", "Export"];

function NavItem({ active = false, children }: { active?: boolean; children: React.ReactNode }) {
  return (
    <button
      className={cn(
        "flex h-8 w-full items-center gap-2 rounded-catty px-2 text-left text-[11px] text-catty-muted transition-colors hover:bg-catty-surface hover:text-catty-text",
        active && "bg-catty-surface text-catty-text",
      )}
    >
      {children}
    </button>
  );
}

export function App() {
  const [episode, setEpisode] = useState<EpisodeMedia | null>(null);
  const [importing, setImporting] = useState(false);
  const [timelineHeight, setTimelineHeight] = useState(280);
  const editorRef = useRef<HTMLElement>(null);
  const playback = usePlayback();

  async function handleImport() {
    if (importing) return;
    setImporting(true);
    try {
      const selected = await importEpisode();
      if (selected) {
        setEpisode(selected);
        playback.setCurrentTime(0);
        playback.setDuration(0);
      }
    } finally {
      setImporting(false);
    }
  }

  function startTimelineResize(event: React.PointerEvent<HTMLDivElement>) {
    const editor = editorRef.current;
    if (!editor) return;
    event.currentTarget.setPointerCapture(event.pointerId);
    const startY = event.clientY;
    const startHeight = timelineHeight;
    const maxHeight = Math.max(220, editor.clientHeight - 180);

    const handleMove = (moveEvent: PointerEvent) => {
      const next = startHeight + (startY - moveEvent.clientY);
      setTimelineHeight(Math.max(180, Math.min(maxHeight, next)));
    };
    const handleUp = () => {
      window.removeEventListener("pointermove", handleMove);
      window.removeEventListener("pointerup", handleUp);
    };
    window.addEventListener("pointermove", handleMove);
    window.addEventListener("pointerup", handleUp);
  }

  return (
    <div className="grid h-screen grid-cols-[190px_minmax(0,1fr)] overflow-hidden bg-catty-bg text-catty-text">
      <aside className="flex flex-col border-r border-catty-border bg-catty-sidebar px-2.5 py-3">
        <div className="flex items-center gap-2.5 px-1.5 pb-3 pt-0.5">
          <div className="grid size-7 place-items-center rounded-catty-lg bg-catty-accent text-xs font-extrabold text-[#160f0b]">
            C
          </div>
          <div className="leading-none">
            <strong className="block text-[13px] leading-[1.1]">Catty</strong>
            <span className="mt-0.5 block text-[9px] leading-[1.1] text-catty-muted">
              Dubber Pro
            </span>
          </div>
        </div>
        <nav className="grid gap-0.5">
          <NavItem active>
            <FolderOpen className="text-catty-accent" size={14} /> Project
          </NavItem>
          <NavItem>
            <Library size={14} /> Episodes
          </NavItem>
          <NavItem>
            <Mic2 size={14} /> Voice Library
          </NavItem>
          <NavItem>
            <Settings size={14} /> Settings
          </NavItem>
        </nav>
        <div className="mt-4 px-1.5">
          <p className="mb-1.5 text-[8px] font-semibold uppercase tracking-[0.12em] text-catty-muted-2">
            Project
          </p>
          <div className="rounded-catty border border-catty-border-subtle bg-catty-panel p-2">
            <div className="flex items-center gap-1.5">
              <Sparkles size={11} className="text-catty-accent" />
              <span className="truncate text-[9px] text-catty-text-soft">Untitled project</span>
            </div>
            <p className="mt-1 text-[8px] text-catty-muted-2">
              {episode ? "1 episode" : "0 episodes"} · Khmer dub
            </p>
          </div>
          {episode && (
            <div className="mt-1.5 rounded-catty border border-catty-border-subtle bg-catty-surface/50 px-2 py-1.5">
              <p className="truncate text-[9px] text-catty-text-soft">{episode.name}</p>
              <p className="mt-0.5 text-[8px] text-catty-muted-2">
                {episode.width && episode.height ? `${episode.width}×${episode.height} · ` : ""}
                {episode.durationSeconds
                  ? `${episode.durationSeconds.toFixed(1)}s`
                  : "Loading metadata…"}
              </p>
            </div>
          )}
        </div>
        <div className="mt-auto border-t border-catty-border-subtle px-1.5 pb-0.5 pt-2.5">
          <div className="flex items-center gap-1.5 text-[9px] text-catty-muted">
            <span className="size-1.5 rounded-full bg-catty-success" />
            Desktop shell ready
          </div>
        </div>
      </aside>

      <main ref={editorRef} className="flex min-h-0 min-w-0 flex-col overflow-hidden">
        <header className="flex h-[52px] shrink-0 items-center justify-between border-b border-catty-border px-3.5">
          <div className="min-w-0">
            <div className="flex items-center gap-2">
              <h1 className="truncate text-[13px] font-semibold">
                {episode?.name ?? "Untitled project"}
              </h1>
              <Badge>{episode ? "Imported" : "Draft"}</Badge>
            </div>
            <p className="mt-0.5 text-[9px] text-catty-muted">
              Dubbing workspace · Chinese/English → Khmer
            </p>
          </div>
          <div className="flex items-center gap-1.5">
            <Button size="sm" disabled={!episode}>
              <WandSparkles size={13} /> Auto dub
            </Button>
            <Button variant="default" size="sm" disabled={importing} onClick={handleImport}>
              <FolderOpen size={13} />{" "}
              {importing ? "Opening…" : episode ? "Replace episode" : "Import episode"}
            </Button>
          </div>
        </header>

        <section className="flex h-9 shrink-0 items-center gap-0.5 overflow-x-auto border-b border-catty-border bg-catty-panel px-3">
          {workflow.map((item, index) => (
            <div
              className={cn(
                "flex h-6 shrink-0 items-center gap-1.5 rounded-catty px-1.5 text-[9px] text-catty-muted-2",
                index === 0 && "bg-catty-accent-soft text-catty-accent-text",
              )}
              key={item}
            >
              <span
                className={cn(
                  "grid size-3.5 place-items-center rounded-full border border-catty-border text-[7px]",
                  index === 0 && "border-catty-accent/60",
                )}
              >
                {index + 1}
              </span>
              {item}
            </div>
          ))}
        </section>

        <section className="grid min-h-[160px] min-w-0 flex-1 grid-cols-[minmax(0,1.45fr)_minmax(280px,0.75fr)] overflow-hidden">
          <VideoPreview
            episode={episode}
            currentTime={playback.currentTime}
            seekRequest={playback.seekRequest}
            onTimeChange={playback.setCurrentTime}
            onMetadata={(metadata) => {
              playback.setDuration(metadata.durationSeconds ?? 0);
              setEpisode((current) => (current ? { ...current, ...metadata } : current));
            }}
          />
          <DialoguePanel />
        </section>

        <div
          className="group relative h-1.5 shrink-0 cursor-row-resize border-y border-catty-border bg-[#171512] hover:bg-catty-accent/25"
          onPointerDown={startTimelineResize}
        >
          <div className="absolute left-1/2 top-1/2 h-px w-8 -translate-x-1/2 -translate-y-1/2 bg-catty-muted-2/50 group-hover:bg-catty-accent" />
        </div>
        <div className="min-h-[180px] shrink-0 overflow-hidden" style={{ height: timelineHeight }}>
          <Timeline episode={episode} currentTime={playback.currentTime} onSeek={playback.seek} />
        </div>
      </main>
    </div>
  );
}
