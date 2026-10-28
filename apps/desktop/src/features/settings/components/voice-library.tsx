import { useEffect, useRef, useState } from "react";

import type { LibraryVoice, VoiceDraft, VoiceEngine } from "@catty/contracts";
import { convertFileSrc } from "@tauri-apps/api/core";
import { open } from "@tauri-apps/plugin-dialog";
import { LoaderCircle, Play, Plus, Trash2 } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectGroup,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";

import { requestEngine } from "../deps/engine";

const NO_BASE_VOICE = "__no_base_voice__";

const isModelDownloading = (model?: { install_status?: string }) =>
  model?.install_status === "downloading" ||
  model?.install_status === "cancelling";

const ENGINE_ITEMS = [
  { label: "Edge TTS", value: "edge" },
  { label: "VoxCPM2", value: "voxcpm2" },
];

const initialDraft = (engine: VoiceEngine): VoiceDraft => ({
  name: "",
  engine,
  gender: "female",
  engine_voice_id: engine === "edge" ? "km-KH-SreymomNeural" : null,
  speed: engine === "edge" ? 1.25 : 1,
  pitch: 0,
  volume: 0,
  style_prompt: "",
});

export function VoiceLibrary({ clone = false }: { clone?: boolean }) {
  const [engine, setEngine] = useState<VoiceEngine>(clone ? "voxcpm2" : "edge");
  const [tab, setTab] = useState<"builtin" | "user">("builtin");
  const [voices, setVoices] = useState<LibraryVoice[]>([]);
  const [draft, setDraft] = useState<VoiceDraft | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [installed, setInstalled] = useState(false);
  const [modelsBusy, setModelsBusy] = useState(false);
  const audio = useRef<HTMLAudioElement | null>(null);
  const mounted = useRef(false);
  const working = useRef(false);
  useEffect(() => {
    mounted.current = true;
    void requestEngine("tts.library_list", {})
      .then((items) => {
        if (mounted.current) setVoices(items);
      })
      .catch((cause: unknown) => {
        if (mounted.current) setError(String(cause));
      });
    void requestEngine("models.list", {})
      .then((items) => {
        if (!mounted.current) return;
        const model = items.find((item) => item.id === "voxcpm2");
        setInstalled(Boolean(model?.installed));
        setModelsBusy(isModelDownloading(model));
      })
      .catch(() => undefined);
    return () => {
      mounted.current = false;
      audio.current?.pause();
      audio.current = null;
    };
  }, []);

  useEffect(() => {
    if (!modelsBusy) return;
    let cancelled = false;
    const timer = window.setInterval(() => {
      void requestEngine("models.list", {})
        .then((items) => {
          if (cancelled) return;
          const model = items.find((item) => item.id === "voxcpm2");
          setInstalled(Boolean(model?.installed));
          setModelsBusy(isModelDownloading(model));
        })
        .catch(() => undefined);
    }, 2000);
    return () => {
      cancelled = true;
      window.clearInterval(timer);
    };
  }, [modelsBusy]);

  async function run(id: string, task: () => Promise<void>) {
    if (working.current) return;
    working.current = true;
    setBusy(id);
    setError(null);
    setNotice(null);
    audio.current?.pause();
    try {
      await task();
    } catch (cause) {
      if (mounted.current)
        setError(cause instanceof Error ? cause.message : String(cause));
    } finally {
      working.current = false;
      if (mounted.current) setBusy(null);
    }
  }
  async function play(params: { voice_id?: string; draft?: VoiceDraft }) {
    const result = await requestEngine("tts.library_preview", params);
    if (!mounted.current) return;
    audio.current?.pause();
    const player = new Audio(convertFileSrc(result.path));
    audio.current = player;
    await player.play();
  }
  const update = (patch: Partial<VoiceDraft>) =>
    setDraft((value) => (value ? { ...value, ...patch } : value));
  const cannotGenerate = engine === "voxcpm2" && !installed;
  const genderItems = [
    { label: `Man${engine === "edge" ? " · Piseth" : ""}`, value: "male" },
    { label: `Woman${engine === "edge" ? " · Sreymom" : ""}`, value: "female" },
  ];
  const baseVoiceItems = [
    { label: "My recording / voice description", value: NO_BASE_VOICE },
    ...voices
      .filter((voice) => voice.engine === "voxcpm2")
      .map((voice) => ({ label: voice.name, value: voice.id })),
  ];
  return (
    <section className="mx-auto max-w-2xl space-y-4" aria-label="Voice library">
      <div className="flex flex-wrap items-center gap-2">
        <h2 className="mr-auto text-sm font-semibold">
          {clone ? "Voice Clone" : "Voices & TTS"}
        </h2>
        <Select
          value={engine}
          items={ENGINE_ITEMS}
          disabled={!!busy}
          onValueChange={(value) => {
            if (!value) return;
            setEngine(value);
            setDraft(null);
            setNotice(null);
            setError(null);
            audio.current?.pause();
          }}
        >
          <SelectTrigger aria-label="TTS engine" className="text-xs">
            <SelectValue />
          </SelectTrigger>
          <SelectContent align="start">
            <SelectGroup>
              {ENGINE_ITEMS.map((item) => (
                <SelectItem key={item.value} value={item.value}>
                  {item.label}
                </SelectItem>
              ))}
            </SelectGroup>
          </SelectContent>
        </Select>
        <Button
          disabled={!!busy}
          onClick={() => setDraft(initialDraft(engine))}
        >
          <Plus />
          Create voice
        </Button>
      </div>
      {engine === "voxcpm2" && (
        <p className="rounded border p-3 text-xs text-muted-foreground">
          {installed
            ? "VoxCPM2 downloaded. The first preview loads the local model and can take longer."
            : "Download VoxCPM2 from Settings → Models to preview or create cloned voices."}{" "}
          Built-in reference samples are generated once and kept in Catty.
          Imported references are copied into the voice library.
        </p>
      )}
      <div
        className="flex gap-2"
        role="group"
        aria-label="Voice library source"
      >
        <Button
          size="sm"
          variant={tab === "builtin" ? "secondary" : "outline"}
          onClick={() => setTab("builtin")}
        >
          Built-in
        </Button>
        <Button
          size="sm"
          variant={tab === "user" ? "secondary" : "outline"}
          onClick={() => setTab("user")}
        >
          My voices
        </Button>
      </div>
      {voices
        .filter((voice) => voice.engine === engine && voice.origin === tab)
        .map((voice) => (
          <div
            key={voice.id}
            className="flex items-center gap-2 rounded border p-3"
          >
            <div className="min-w-0 flex-1">
              <p className="truncate text-xs font-medium">{voice.name}</p>
              <p className="text-[10px] text-muted-foreground">
                {engine === "edge"
                  ? `${voice.engine_voice_id} · ${voice.speed}× · ${voice.pitch} Hz`
                  : `${voice.gender || "Custom"} · ${voice.style_prompt || "Reference voice"}`}
              </p>
            </div>
            <Button
              size="sm"
              variant="outline"
              aria-label={`Preview ${voice.name}`}
              disabled={!!busy || cannotGenerate}
              onClick={() =>
                void run(voice.id, () => play({ voice_id: voice.id }))
              }
            >
              {busy === voice.id ? (
                <LoaderCircle className="animate-spin" />
              ) : (
                <Play />
              )}
              Sample
            </Button>
            <Button
              size="sm"
              variant="ghost"
              disabled={!!busy}
              onClick={() => {
                setDraft({
                  ...initialDraft(engine),
                  name: `${voice.name} copy`,
                  gender: voice.gender,
                  engine_voice_id: voice.engine_voice_id,
                  speed: voice.speed,
                  pitch: voice.pitch,
                  volume: voice.volume,
                  style_prompt: voice.style_prompt,
                  base_voice_id: engine === "voxcpm2" ? voice.id : null,
                });
              }}
            >
              Customize
            </Button>
            {voice.origin === "user" && (
              <Button
                size="icon-sm"
                variant="ghost"
                aria-label={`Delete ${voice.name}`}
                disabled={!!busy}
                onClick={() =>
                  void run(voice.id, async () => {
                    await requestEngine("tts.library_remove", {
                      voice_id: voice.id,
                    });
                    const items = await requestEngine("tts.library_list", {});
                    if (mounted.current) {
                      setVoices(items);
                      window.dispatchEvent(new Event("catty:voices-changed"));
                      setNotice(
                        "Voice removed from My voices. Existing project copies are preserved.",
                      );
                    }
                  })
                }
              >
                <Trash2 />
              </Button>
            )}
          </div>
        ))}
      {!voices.some(
        (voice) => voice.engine === engine && voice.origin === tab,
      ) && (
        <p className="text-xs text-muted-foreground">
          No saved voices yet. Choose Create voice to add one.
        </p>
      )}
      {draft && (
        <div
          className="space-y-3 rounded-lg border p-4"
          aria-label="Create voice profile"
        >
          <h3 className="text-xs font-semibold">
            Create {engine === "edge" ? "Edge preset" : "VoxCPM2 voice"}
          </h3>
          <label className="block space-y-1 text-xs">
            Name
            <Input
              aria-label="Voice profile name"
              maxLength={100}
              value={draft.name}
              onChange={(event) => update({ name: event.target.value })}
              disabled={!!busy}
            />
          </label>
          <label className="block space-y-1 text-xs">
            {engine === "edge" ? "Base voice" : "Voice gender"}
            <Select
              value={draft.gender}
              items={genderItems}
              disabled={!!busy}
              onValueChange={(value) => {
                if (!value) return;
                update({
                  gender: value,
                  engine_voice_id:
                    engine === "edge"
                      ? value === "male"
                        ? "km-KH-PisethNeural"
                        : "km-KH-SreymomNeural"
                      : null,
                });
              }}
            >
              <SelectTrigger
                aria-label="Base voice gender"
                className="w-full text-xs"
              >
                <SelectValue />
              </SelectTrigger>
              <SelectContent align="start">
                <SelectGroup>
                  {genderItems.map((item) => (
                    <SelectItem key={item.value} value={item.value}>
                      {item.label}
                    </SelectItem>
                  ))}
                </SelectGroup>
              </SelectContent>
            </Select>
          </label>
          {engine === "edge" ? (
            <div className="flex gap-2">
              {(["speed", "pitch", "volume"] as const).map((field) => (
                <label key={field} className="min-w-0 flex-1 text-xs">
                  {field}
                  <Input
                    aria-label={`Preset ${field}`}
                    type="number"
                    min={field === "speed" ? 0.5 : -100}
                    max={field === "speed" ? 2 : 100}
                    step={field === "speed" ? 0.05 : 1}
                    disabled={!!busy}
                    value={draft[field]}
                    onChange={(event) => {
                      if (event.target.value !== "")
                        update({ [field]: Number(event.target.value) });
                    }}
                  />
                </label>
              ))}
            </div>
          ) : (
            <>
              <p className="text-[10px] text-muted-foreground">
                Use a built-in reference, import a clear 3–30 second voice clip,
                or describe a new voice. Changing gender is descriptive; the
                reference determines voice identity.
              </p>
              <label className="block space-y-1 text-xs">
                Starting voice
                <Select
                  value={draft.base_voice_id ?? NO_BASE_VOICE}
                  items={baseVoiceItems}
                  disabled={!!busy}
                  onValueChange={(value) => {
                    if (!value) return;
                    update({
                      base_voice_id: value === NO_BASE_VOICE ? null : value,
                      reference_audio_path: null,
                      reference_text: null,
                    });
                  }}
                >
                  <SelectTrigger
                    aria-label="Starting reference voice"
                    className="w-full text-xs"
                  >
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent align="start">
                    <SelectGroup>
                      {baseVoiceItems.map((item) => (
                        <SelectItem key={item.value} value={item.value}>
                          {item.label}
                        </SelectItem>
                      ))}
                    </SelectGroup>
                  </SelectContent>
                </Select>
              </label>
              <Button
                size="sm"
                variant="outline"
                disabled={!!busy}
                onClick={() =>
                  void run("import", async () => {
                    const path = await open({
                      multiple: false,
                      directory: false,
                      filters: [
                        {
                          name: "Voice reference",
                          extensions: ["wav", "mp3", "m4a", "flac", "ogg"],
                        },
                      ],
                    });
                    if (path && typeof path === "string" && mounted.current)
                      update({
                        reference_audio_path: path,
                        base_voice_id: null,
                      });
                  })
                }
              >
                Import reference audio
              </Button>
              {draft.reference_audio_path && (
                <p className="break-all text-[10px] text-muted-foreground">
                  {draft.reference_audio_path}
                </p>
              )}
              {draft.reference_audio_path && (
                <label className="block space-y-1 text-xs">
                  Reference transcript (optional)
                  <textarea
                    aria-label="Reference transcript"
                    className="w-full rounded border bg-background p-2"
                    disabled={!!busy}
                    value={draft.reference_text ?? ""}
                    maxLength={10000}
                    onChange={(event) =>
                      update({ reference_text: event.target.value || null })
                    }
                  />
                </label>
              )}
              <label className="block space-y-1 text-xs">
                Voice / style description
                <textarea
                  aria-label="Voice style description"
                  className="w-full rounded border bg-background p-2"
                  placeholder="An elderly woman with a warm, gentle voice"
                  disabled={!!busy}
                  value={draft.style_prompt ?? ""}
                  maxLength={2000}
                  onChange={(event) =>
                    update({ style_prompt: event.target.value })
                  }
                />
              </label>
            </>
          )}
          <div className="flex gap-2">
            <Button
              size="sm"
              variant="outline"
              disabled={!!busy || cannotGenerate}
              onClick={() =>
                void run("preview", () =>
                  play({
                    draft: { ...draft, name: draft.name.trim() || "Preview" },
                  }),
                )
              }
            >
              {busy === "preview" ? (
                <LoaderCircle className="animate-spin" />
              ) : (
                <Play />
              )}
              Preview Khmer sample
            </Button>
            <Button
              size="sm"
              disabled={!!busy || !draft.name.trim() || cannotGenerate}
              onClick={() =>
                void run("save", async () => {
                  await requestEngine("tts.library_create", draft);
                  const items = await requestEngine("tts.library_list", {});
                  if (mounted.current) {
                    setVoices(items);
                    setDraft(null);
                    setTab("user");
                    window.dispatchEvent(new Event("catty:voices-changed"));
                    setNotice(
                      "Voice saved and available in the editor voice selectors.",
                    );
                  }
                })
              }
            >
              {busy === "save" && <LoaderCircle className="animate-spin" />}Save
              voice
            </Button>
            <Button
              size="sm"
              variant="ghost"
              disabled={!!busy}
              onClick={() => setDraft(null)}
            >
              Cancel
            </Button>
          </div>
        </div>
      )}
      {busy && (
        <p role="status" className="text-xs text-muted-foreground">
          {busy === "import"
            ? "Choosing reference audio…"
            : "Preparing voice… Model loading and local generation may take a while."}
        </p>
      )}
      {error && (
        <p role="alert" className="text-xs text-destructive">
          {error}
        </p>
      )}
      {notice && (
        <p role="status" className="text-xs text-muted-foreground">
          {notice}
        </p>
      )}
    </section>
  );
}
