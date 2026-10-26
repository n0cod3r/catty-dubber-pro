import { useState } from "react";

import { Film, Languages, MessageSquareText } from "lucide-react";

import type { EpisodeMedia } from "@/features/episodes/types";
import { formatTime } from "@/features/timeline/geometry";
import { cn } from "@/lib/utils";

const tabs = [
  { id: "source", label: "Dialogue", icon: MessageSquareText },
  { id: "translation", label: "Khmer", icon: Languages },
  { id: "properties", label: "Media", icon: Film },
] as const;

export function DialoguePanel({ episode }: { episode: EpisodeMedia | null }) {
  const [tab, setTab] = useState<(typeof tabs)[number]["id"]>("source");
  return (
    <section
      className="flex min-h-0 min-w-0 flex-1 flex-col bg-card"
      aria-label="Dialogue and media inspector"
    >
      <div className="flex h-9 shrink-0 items-center justify-between border-b px-3 text-[11px] font-medium">
        Inspector
        <span className="rounded border px-1.5 py-0.5 text-[9px] font-normal text-muted-foreground">
          {tab === "properties" ? "Source" : "0 lines"}
        </span>
      </div>
      <div role="tablist" aria-label="Inspector panels" className="flex h-9 shrink-0 border-b">
        {tabs.map(({ id, label, icon: Icon }, index) => (
          <button
            key={id}
            id={`inspector-tab-${id}`}
            role="tab"
            aria-selected={tab === id}
            aria-controls={`inspector-panel-${id}`}
            tabIndex={tab === id ? 0 : -1}
            className={cn(
              "flex flex-1 items-center justify-center gap-1.5 border-b-2 border-transparent text-[10px] text-muted-foreground outline-none focus-visible:ring-1 focus-visible:ring-inset focus-visible:ring-ring",
              tab === id && "border-primary bg-background/40 text-foreground",
            )}
            onClick={() => setTab(id)}
            onKeyDown={(event) => {
              const next =
                event.key === "ArrowRight"
                  ? (index + 1) % tabs.length
                  : event.key === "ArrowLeft"
                    ? (index + tabs.length - 1) % tabs.length
                    : event.key === "Home"
                      ? 0
                      : event.key === "End"
                        ? tabs.length - 1
                        : null;
              const nextTab = next === null ? undefined : tabs[next];
              if (nextTab) {
                event.preventDefault();
                setTab(nextTab.id);
                document.getElementById(`inspector-tab-${nextTab.id}`)?.focus();
              }
            }}
          >
            <Icon className="size-3" />
            {label}
          </button>
        ))}
      </div>
      <div
        role="tabpanel"
        id={`inspector-panel-${tab}`}
        aria-labelledby={`inspector-tab-${tab}`}
        tabIndex={0}
        className="flex min-h-0 flex-1 flex-col overflow-auto p-4 outline-none focus-visible:ring-1 focus-visible:ring-inset focus-visible:ring-ring"
      >
        {tab === "properties" && episode ? (
          <dl className="space-y-4 text-[11px]">
            {[
              ["File", episode.name],
              ["Container", episode.extension.toUpperCase()],
              ["Duration", formatTime(episode.durationSeconds ?? 0, true)],
              [
                "Resolution",
                episode.width && episode.height
                  ? `${episode.width} × ${episode.height}`
                  : "Reading…",
              ],
              ["Target language", "Khmer"],
              ...(episode.fps ? [["Frame rate", `${episode.fps.toFixed(3)} fps`]] : []),
              ...(episode.videoCodec ? [["Video codec", episode.videoCodec]] : []),
              ...(episode.audioCodec ? [["Audio codec", episode.audioCodec]] : []),
              ...(episode.sampleRate ? [["Audio sample rate", `${episode.sampleRate} Hz`]] : []),
            ].map(([label, value]) => (
              <div key={label}>
                <dt className="mb-1 text-[10px] text-muted-foreground">{label}</dt>
                <dd className="break-words">{value}</dd>
              </div>
            ))}
          </dl>
        ) : (
          <div className="m-auto text-center">
            <MessageSquareText
              className="mx-auto mb-3 size-7 text-muted-foreground/50"
              strokeWidth={1.3}
            />
            <p className="text-xs font-medium">
              {tab === "translation"
                ? "No translations yet"
                : tab === "properties"
                  ? "No media selected"
                  : "No dialogue yet"}
            </p>
            <p className="mt-2 max-w-[230px] text-[11px] leading-relaxed text-muted-foreground">
              {tab === "translation"
                ? "Khmer translations and speaker assignments will appear here when translation is connected."
                : tab === "properties"
                  ? "Import an episode to inspect its duration and resolution."
                  : "The transcription engine is not connected yet. Imported video and source audio are available on the timeline."}
            </p>
          </div>
        )}
      </div>
      <div className="flex h-7 shrink-0 items-center justify-between border-t px-3 text-[9px] text-muted-foreground">
        <span>Source → Khmer</span>
        <span>Inspector</span>
      </div>
    </section>
  );
}
