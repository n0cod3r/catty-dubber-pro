import { useEffect, useState } from "react";

import type { TranscriptSegment } from "@catty/contracts";
import { Film, Languages, LoaderCircle, MessageSquareText, Sparkles } from "lucide-react";

import { Button } from "@/components/ui/button";
import type { EpisodeMedia } from "@/features/editor/deps/episodes";
import { requestEngine } from "@/features/episodes/deps/engine";
import { cn } from "@/lib/utils";
import { formatTime } from "@/shared/utils/time";

const tabs = [
  { id: "source", label: "Dialogue", icon: MessageSquareText },
  { id: "translation", label: "Khmer", icon: Languages },
  { id: "properties", label: "Media", icon: Film },
] as const;
const transcriptionEngines = [
  { id: "paraformer", label: "Paraformer" },
  { id: "sense-small", label: "SenseSmall" },
] as const;
type TranscriptionEngine = (typeof transcriptionEngines)[number]["id"];
type DialogueRow = TranscriptSegment & { id: string };
const TRANSCRIPTION_ENGINE_KEY = "catty.transcription-engine.v1";
function readTranscriptionEngine(): TranscriptionEngine {
  if (typeof window === "undefined") return "paraformer";
  return window.localStorage.getItem(TRANSCRIPTION_ENGINE_KEY) === "sense-small" ? "sense-small" : "paraformer";
}
function persistedSegments(episode: EpisodeMedia | null): DialogueRow[] {
  return (episode?.dialogueSegments ?? []).map((segment) => ({
    id: segment.id,
    start: segment.start,
    end: segment.end,
    text: segment.sourceText,
    confidence: segment.confidence,
  }));
}

export function Inspector({
  episode,
  projectDirectory,
  onSeek,
  onDialogueChange,
}: {
  episode: EpisodeMedia | null;
  projectDirectory: string;
  onSeek: (time: number) => void;
  onDialogueChange: (segments: DialogueRow[]) => void;
}) {
  const [tab, setTab] = useState<(typeof tabs)[number]["id"]>("source");
  const [engine, setEngine] = useState<TranscriptionEngine>(readTranscriptionEngine);
  const [transcribing, setTranscribing] = useState(false);
  const [segments, setSegments] = useState<DialogueRow[]>(() => persistedSegments(episode));
  const [transcriptionError, setTranscriptionError] = useState<string | null>(null);
  useEffect(() => window.localStorage.setItem(TRANSCRIPTION_ENGINE_KEY, engine), [engine]);
  useEffect(() => {
    const restored = persistedSegments(episode);
    setSegments(restored);
    onDialogueChange(restored);
    setTranscriptionError(null);
  }, [episode?.id, episode?.dialogueSegments, onDialogueChange]);

  const transcribe = async () => {
    if (!episode?.durationSeconds || transcribing) return;
    setTranscribing(true);
    setTranscriptionError(null);
    try {
      const result = await requestEngine("speech.transcribe", {
        project_directory: projectDirectory,
        episode_id: episode.id,
        source: episode.path,
        source_start: 0,
        duration: episode.durationSeconds,
        language: "zh",
        asr_backend: engine,
        asr_config: {},
        vad_backend: "silero",
        vad_config: {},
      });
      const next = result.segments.map((segment, index) => ({
        ...segment,
        id: `${segment.start.toFixed(3)}-${segment.end.toFixed(3)}-${index}`,
      }));
      setSegments(next);
      onDialogueChange(next);
    } catch (cause) {
      setTranscriptionError(cause instanceof Error ? cause.message : "មិនអាច Transcribe បានទេ។");
    } finally {
      setTranscribing(false);
    }
  };

  return (
    <section className="flex min-h-0 min-w-0 flex-1 flex-col bg-card" aria-label="Dialogue and media inspector">
      <div className="flex h-9 shrink-0 items-center justify-between border-b px-3 text-[11px] font-medium">
        Inspector
        <span className="rounded border px-1.5 py-0.5 text-[9px] font-normal text-muted-foreground">{tab === "properties" ? "Source" : `${segments.length} lines`}</span>
      </div>
      <div role="tablist" aria-label="Inspector panels" className="flex h-9 shrink-0 border-b">
        {tabs.map(({ id, label, icon: Icon }, index) => (
          <button key={id} id={`inspector-tab-${id}`} role="tab" aria-selected={tab === id} aria-controls={`inspector-panel-${id}`} tabIndex={tab === id ? 0 : -1} className={cn("flex flex-1 items-center justify-center gap-1.5 border-b-2 border-transparent text-[10px] text-muted-foreground outline-none focus-visible:ring-1 focus-visible:ring-inset focus-visible:ring-ring", tab === id && "border-primary bg-background/40 text-foreground")} onClick={() => setTab(id)} onKeyDown={(event) => { const next = event.key === "ArrowRight" ? (index + 1) % tabs.length : event.key === "ArrowLeft" ? (index + tabs.length - 1) % tabs.length : event.key === "Home" ? 0 : event.key === "End" ? tabs.length - 1 : null; const nextTab = next === null ? undefined : tabs[next]; if (nextTab) { event.preventDefault(); setTab(nextTab.id); document.getElementById(`inspector-tab-${nextTab.id}`)?.focus(); } }}><Icon className="size-3" />{label}</button>
        ))}
      </div>
      <div role="tabpanel" id={`inspector-panel-${tab}`} aria-labelledby={`inspector-tab-${tab}`} tabIndex={0} className="flex min-h-0 flex-1 flex-col overflow-auto outline-none focus-visible:ring-1 focus-visible:ring-inset focus-visible:ring-ring">
        {tab === "properties" && episode ? (
          <dl className="space-y-4 p-4 text-[11px]">{[["File", episode.name], ["Container", episode.extension.toUpperCase()], ["Duration", formatTime(episode.durationSeconds ?? 0, true)], ["Resolution", episode.width && episode.height ? `${episode.width} × ${episode.height}` : "Reading…"], ["Target language", "Khmer"], ...(episode.fps ? [["Frame rate", `${episode.fps.toFixed(3)} fps`]] : []), ...(episode.videoCodec ? [["Video codec", episode.videoCodec]] : []), ...(episode.audioCodec ? [["Audio codec", episode.audioCodec]] : []), ...(episode.sampleRate ? [["Audio sample rate", `${episode.sampleRate} Hz`]] : [])].map(([label, value]) => <div key={label}><dt className="mb-1 text-[10px] text-muted-foreground">{label}</dt><dd className="break-words">{value}</dd></div>)}</dl>
        ) : tab === "source" ? (
          segments.length > 0 ? (
            <div className="flex min-h-0 flex-1 flex-col">
              <div className="flex h-9 shrink-0 items-center justify-between border-b px-2">
                <div className="flex items-center rounded-md border bg-muted/30 p-0.5" role="group" aria-label="Transcription engine">
                  {transcriptionEngines.map((item) => <Button key={item.id} type="button" size="xs" variant={engine === item.id ? "secondary" : "ghost"} aria-pressed={engine === item.id} className="h-5 px-1.5 text-[9px]" disabled={transcribing} onClick={() => setEngine(item.id)}>{item.label}</Button>)}
                </div>
                <Button size="xs" variant="outline" className="h-6 text-[9px]" disabled={transcribing} onClick={() => void transcribe()}>{transcribing && <LoaderCircle className="animate-spin" />}Re-transcribe</Button>
              </div>
              <div className="grid h-7 shrink-0 grid-cols-[28px_86px_minmax(0,1fr)] items-center border-b bg-muted/20 px-2 text-[9px] font-medium text-muted-foreground">
                <span>#</span><span>Time</span><span>Dialogue</span>
              </div>
              <div className="min-h-0 flex-1 overflow-auto">
                {segments.map((segment, index) => (
                  <button key={segment.id} type="button" className="grid w-full grid-cols-[28px_86px_minmax(0,1fr)] items-start border-b px-2 py-1.5 text-left hover:bg-muted/40 focus-visible:bg-muted/50 focus-visible:outline-none" onClick={() => onSeek(segment.start)}>
                    <span className="pt-0.5 text-[9px] tabular-nums text-muted-foreground">{index + 1}</span>
                    <span className="pt-0.5 text-[9px] tabular-nums text-muted-foreground">{formatTime(segment.start, true)}</span>
                    <span className="min-w-0 text-[11px] leading-[1.45]">{segment.text}</span>
                  </button>
                ))}
              </div>
              {transcriptionError && <p role="alert" className="border-t px-2 py-1.5 text-[10px] text-destructive">{transcriptionError}</p>}
            </div>
          ) : (
            <div className="m-auto flex w-full max-w-[270px] flex-col items-center p-4 text-center"><MessageSquareText className="mb-3 size-7 text-muted-foreground/50" strokeWidth={1.3} /><p className="text-xs font-medium">{episode ? "No dialogue yet" : "No media selected"}</p><p className="mt-2 text-[11px] leading-relaxed text-muted-foreground">{episode ? "ជ្រើស engine ហើយចុច Transcribe។ Catty នឹងបង្កើត Dialogue និង Subtitle timeline ដោយស្វ័យប្រវត្តិ។" : "Import an episode to start transcription and dubbing."}</p>{episode && <div className="mt-3 flex items-center rounded-md border bg-muted/30 p-0.5" role="group" aria-label="Transcription engine">{transcriptionEngines.map((item) => <Button key={item.id} type="button" size="xs" variant={engine === item.id ? "secondary" : "ghost"} aria-pressed={engine === item.id} className="h-6 px-2 text-[10px]" disabled={transcribing} onClick={() => setEngine(item.id)}>{item.label}</Button>)}</div>}<Button size="xs" className="mt-2" disabled={!episode?.durationSeconds || transcribing} onClick={() => void transcribe()}>{transcribing ? <LoaderCircle className="animate-spin" /> : <Sparkles />}{transcribing ? "កំពុង Transcribe…" : "Transcribe"}</Button>{episode && <p className="mt-2 text-[9px] text-muted-foreground/70">Chinese · {engine === "paraformer" ? "Paraformer" : "SenseSmall"} · Auto VAD</p>}{transcriptionError && <p role="alert" className="mt-2 text-[10px] text-destructive">{transcriptionError}</p>}</div>
          )
        ) : (
          <div className="m-auto p-4 text-center"><Languages className="mx-auto mb-3 size-7 text-muted-foreground/50" strokeWidth={1.3} /><p className="text-xs font-medium">{episode ? "No Khmer translation yet" : "No media selected"}</p><p className="mt-2 max-w-[230px] text-[11px] leading-relaxed text-muted-foreground">{episode ? "Translate dialogue after transcription. Translation will stay linked to its source timing and speaker." : "Import and transcribe an episode before translating it."}</p></div>
        )}
      </div>
      <div className="flex h-7 shrink-0 items-center justify-between border-t px-3 text-[9px] text-muted-foreground"><span>Source → Khmer</span><span>{episode ? "AI dubbing" : "Inspector"}</span></div>
    </section>
  );
}
