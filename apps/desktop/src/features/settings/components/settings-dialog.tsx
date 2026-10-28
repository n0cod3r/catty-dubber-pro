import { useEffect, useMemo, useState, type ReactNode } from "react";

import type {
  AppSettings,
  ComputeDevice,
  SettingsSnapshot,
  TranslationModel,
  TranslationProviderId,
  TranslationStyle,
} from "@catty/contracts";
import {
  AlertCircle,
  AudioLines,
  Bot,
  Check as CheckIcon,
  Database,
  Download,
  Gauge,
  HardDrive,
  Info,
  Keyboard,
  KeyRound,
  Languages,
  Loader2,
  Plus,
  Search,
  Settings2,
  Trash2,
  X,
} from "lucide-react";

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
import { VoiceLibrary } from "./voice-library";

const pages = [
  ["general", "ទូទៅ", "General", Settings2],
  ["translation", "ការបកប្រែ", "Translation", Languages],
  ["models", "ម៉ូដែល", "Models", Database],
  ["tts", "សំឡេង & TTS", "Voices & TTS", AudioLines],
  ["clone", "ចម្លងសំឡេង", "Voice Clone", Bot],
  ["performance", "ដំណើរការ", "Performance", Gauge],
  ["storage", "ទីតាំងផ្ទុក", "Storage", HardDrive],
  ["shortcuts", "ផ្លូវកាត់", "Shortcuts", Keyboard],
  ["about", "អំពី Catty", "About", Info],
] as const;
type PageId = (typeof pages)[number][0];
const providerLabels: Record<TranslationProviderId, string> = {
  local: "Local",
  gemini: "Gemini",
  deepseek: "DeepSeek",
  google: "Google Cloud",
  baidu: "Baidu",
  openai_compatible: "OpenAI-compatible",
};
const providers = Object.keys(providerLabels) as TranslationProviderId[];
const targetLanguageItems = [{ label: "ខ្មែរ (Khmer)", value: "km" }];
const translationStyleItems = [
  { label: "Natural Dubbing", value: "natural_dubbing" },
  { label: "Accurate / Literal", value: "literal" },
  { label: "Short & Conversational", value: "short_conversational" },
];
const languageItems = [
  { label: "ខ្មែរ", value: "km" },
  { label: "English", value: "en" },
];
const computeDeviceItems = ["auto", "cpu", "cuda", "mps"].map((device) => ({
  label: device.toUpperCase(),
  value: device,
}));
type Props = { open: boolean; onOpenChange: (open: boolean) => void };

export function SettingsDialog({ open, onOpenChange }: Props) {
  const [page, setPage] = useState<PageId>("translation");
  const [query, setQuery] = useState("");
  const [snapshot, setSnapshot] = useState<SettingsSnapshot | null>(null);
  const [draft, setDraft] = useState<AppSettings | null>(null);
  const [credential, setCredential] = useState("");
  const [models, setModels] = useState<TranslationModel[]>([]);
  const [localModels, setLocalModels] = useState<TranslationModel[]>([]);
  const [busy, setBusy] = useState<
    "load" | "save" | "models" | "test" | "credential" | "model-action" | null
  >(null);
  const [modelActionId, setModelActionId] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [loadRevision, setLoadRevision] = useState(0);

  useEffect(() => {
    if (!open) return;
    let cancelled = false;
    setBusy("load");
    setLoadError(null);
    setMessage(null);
    setCredential("");
    setModels([]);
    setLocalModels([]);
    void requestEngine("settings.get", {})
      .then((value) => {
        if (cancelled) return;
        setSnapshot(value);
        setDraft(structuredClone(value.settings));
      })
      .catch((error: unknown) => {
        if (cancelled) return;
        setDraft(null);
        setSnapshot(null);
        setLoadError(
          error instanceof Error ? error.message : "Could not load settings.",
        );
      })
      .finally(() => {
        if (!cancelled) setBusy(null);
      });
    void requestEngine("models.list", {})
      .then((value) => {
        if (!cancelled) setLocalModels(value);
      })
      .catch((error: unknown) => {
        if (!cancelled)
          setMessage(
            error instanceof Error
              ? error.message
              : "Could not load local models.",
          );
      });
    return () => {
      cancelled = true;
    };
  }, [open, loadRevision]);

  const modelsBusy = localModels.some(
    (model) =>
      model.install_status === "downloading" ||
      model.install_status === "cancelling",
  );

  useEffect(() => {
    if (!open || !modelsBusy) return;
    let cancelled = false;
    const timer = window.setInterval(() => {
      void requestEngine("models.list", {})
        .then((value) => {
          if (!cancelled) setLocalModels(value);
        })
        .catch(() => undefined);
    }, 1000);
    return () => {
      cancelled = true;
      window.clearInterval(timer);
    };
  }, [open, modelsBusy]);

  const provider = draft?.translation.provider ?? "local";
  const configured = snapshot?.credentials[provider] ?? false;
  const credentialIds = snapshot?.credential_ids?.[provider] ?? [];

  useEffect(() => {
    if (!open || provider !== "gemini" || !configured || credential.trim())
      return;
    let cancelled = false;
    setBusy("models");
    setMessage(null);
    void requestEngine("translation.models", {
      provider: "gemini",
      credential: null,
    })
      .then((value) => {
        if (!cancelled) setModels(value);
      })
      .catch((error: unknown) => {
        if (!cancelled)
          setMessage(
            error instanceof Error
              ? error.message
              : "Could not load Gemini models.",
          );
      })
      .finally(() => {
        if (!cancelled)
          setBusy((current) => (current === "models" ? null : current));
      });
    return () => {
      cancelled = true;
    };
  }, [open, provider, configured, credential]);

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    return q
      ? pages.filter(([, l, h]) => `${l} ${h}`.toLowerCase().includes(q))
      : pages;
  }, [query]);
  if (!open) return null;
  const selected = pages.find(([id]) => id === page) ?? pages[0];

  async function refreshModels() {
    if (!draft) return;
    setBusy("models");
    setMessage(null);
    try {
      if (provider === "local")
        setLocalModels(await requestEngine("models.list", {}));
      else
        setModels(
          await requestEngine("translation.models", {
            provider,
            credential: credential.trim() || null,
          }),
        );
    } catch (e) {
      setMessage(e instanceof Error ? e.message : "Could not load models.");
    } finally {
      setBusy(null);
    }
  }
  async function modelAction(modelId: string, action: "install" | "remove") {
    setBusy("model-action");
    setModelActionId(modelId);
    setMessage(
      action === "install"
        ? "Starting or resuming model download…"
        : "Updating local model…",
    );
    try {
      if (action === "install") {
        const started = await requestEngine("models.install", {
          model_id: modelId,
        });
        setLocalModels((current) =>
          current.map((model) => (model.id === modelId ? started : model)),
        );
        setMessage("Model download is running in the background.");
      } else {
        const result = await requestEngine("models.remove", {
          model_id: modelId,
        });
        setLocalModels(await requestEngine("models.list", {}));
        if (result.install_status === "cancelling") {
          setMessage(
            "Cancelling download… Partial files will be kept so you can resume later.",
          );
        } else if (
          result.install_status === "cancelled" &&
          (result.downloaded_bytes ?? 0) > 0
        ) {
          setMessage(
            "Download stopped. Partial files are kept so you can resume later.",
          );
        } else {
          setMessage("Model data removed.");
          if (draft?.translation.providers.local.selected_model === modelId)
            setDraft({
              ...draft,
              translation: {
                ...draft.translation,
                providers: {
                  ...draft.translation.providers,
                  local: {
                    ...draft.translation.providers.local,
                    selected_model: null,
                  },
                },
              },
            });
        }
      }
    } catch (e) {
      setMessage(e instanceof Error ? e.message : `Could not ${action} model.`);
    } finally {
      setModelActionId(null);
      setBusy(null);
    }
  }
  async function testConnection() {
    setBusy("test");
    setMessage(null);
    try {
      const r = await requestEngine("translation.test_connection", {
        provider,
        credential: credential.trim() || null,
      });
      setMessage(r.message);
    } catch (e) {
      setMessage(e instanceof Error ? e.message : "Connection test failed.");
    } finally {
      setBusy(null);
    }
  }
  async function addCredential() {
    if (provider === "local" || !credential.trim()) return;
    setBusy("credential");
    setMessage(null);
    try {
      const value = await requestEngine("settings.credential_add", {
        provider,
        secret: credential.trim(),
      });
      setSnapshot(value);
      setDraft(structuredClone(value.settings));
      setCredential("");
      setMessage(
        "API key saved securely. Catty can rotate to it automatically.",
      );
    } catch (e) {
      setMessage(e instanceof Error ? e.message : "Could not add API key.");
    } finally {
      setBusy(null);
    }
  }
  async function removeCredential(id: string) {
    if (provider === "local") return;
    setBusy("credential");
    setMessage(null);
    try {
      const value = await requestEngine("settings.credential_remove", {
        provider,
        credential_id: id,
      });
      setSnapshot(value);
      setDraft(structuredClone(value.settings));
      setMessage("API key removed.");
    } catch (e) {
      setMessage(e instanceof Error ? e.message : "Could not remove API key.");
    } finally {
      setBusy(null);
    }
  }
  async function save() {
    if (!draft) return;
    setBusy("save");
    setMessage(null);
    try {
      const value = await requestEngine("settings.update", {
        settings: draft,
        credentials: {},
      });
      setSnapshot(value);
      setDraft(structuredClone(value.settings));
      onOpenChange(false);
    } catch (e) {
      setMessage(e instanceof Error ? e.message : "Could not save settings.");
    } finally {
      setBusy(null);
    }
  }

  return (
    <div
      className="fixed inset-0 z-[100] grid place-items-center bg-black/45 p-4 backdrop-blur-[2px]"
      onMouseDown={() => onOpenChange(false)}
    >
      <section
        role="dialog"
        aria-modal="true"
        aria-label="Catty Settings"
        onMouseDown={(e) => e.stopPropagation()}
        className="flex h-[min(720px,90vh)] w-[min(940px,94vw)] min-h-[520px] overflow-hidden rounded-xl border bg-background shadow-2xl"
      >
        <aside className="flex w-56 shrink-0 flex-col border-r bg-muted/20">
          <div className="flex h-12 items-center gap-2 border-b px-3">
            <div className="grid size-7 place-items-center rounded-md bg-primary/15 text-primary">
              <Settings2 className="size-4" />
            </div>
            <div>
              <p className="text-xs font-semibold">ការកំណត់</p>
              <p className="text-[9px] text-muted-foreground">
                Catty Dubber Pro
              </p>
            </div>
          </div>
          <div className="p-2">
            <div className="relative">
              <Search className="absolute left-2 top-1/2 size-3.5 -translate-y-1/2 text-muted-foreground" />
              <Input
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                placeholder="ស្វែងរក..."
                className="h-8 pl-7 text-xs"
              />
            </div>
          </div>
          <nav className="min-h-0 flex-1 overflow-auto px-2">
            {filtered.map(([id, label, hint, Icon]) => (
              <button
                key={id}
                onClick={() => setPage(id)}
                className={`mb-0.5 flex w-full items-center gap-2 rounded-md px-2 py-1.5 text-left ${page === id ? "bg-primary/12 text-primary" : "text-muted-foreground hover:bg-muted"}`}
              >
                <Icon className="size-3.5" />
                <span>
                  <span className="block text-[11px] font-medium text-foreground">
                    {label}
                  </span>
                  <span className="block text-[9px]">{hint}</span>
                </span>
              </button>
            ))}
          </nav>
          <div className="border-t px-3 py-2 text-[9px] text-muted-foreground">
            Khmer-first · Local-first
          </div>
        </aside>
        <div className="flex min-w-0 flex-1 flex-col">
          <header className="flex h-12 items-center border-b px-4">
            <div>
              <h2 className="text-sm font-semibold">{selected[1]}</h2>
              <p className="text-[10px] text-muted-foreground">{selected[2]}</p>
            </div>
            <Button
              variant="ghost"
              size="icon-xs"
              className="ml-auto"
              onClick={() => onOpenChange(false)}
            >
              <X />
            </Button>
          </header>
          <main className="min-h-0 flex-1 overflow-auto p-4">
            {busy === "load" ? (
              <div className="grid h-full place-items-center">
                <div className="flex items-center gap-2 text-xs text-muted-foreground">
                  <Loader2 className="size-4 animate-spin" />
                  កំពុងផ្ទុកការកំណត់…
                </div>
              </div>
            ) : loadError ? (
              <LoadError
                error={loadError}
                retry={() => setLoadRevision((value) => value + 1)}
              />
            ) : draft ? (
              page === "translation" ? (
                <TranslationPage
                  draft={draft}
                  setDraft={setDraft}
                  credential={credential}
                  setCredential={setCredential}
                  configured={configured}
                  credentialIds={credentialIds}
                  models={models}
                  localModels={localModels}
                  busy={busy}
                  refreshModels={refreshModels}
                  testConnection={testConnection}
                  addCredential={addCredential}
                  removeCredential={removeCredential}
                />
              ) : page === "models" ? (
                <ModelsPage
                  models={localModels}
                  selectedModel={
                    draft.translation.providers.local.selected_model
                  }
                  busy={busy}
                  modelActionId={modelActionId}
                  onInstall={(id) => void modelAction(id, "install")}
                  onRemove={(id) => void modelAction(id, "remove")}
                  onSelect={(id) =>
                    setDraft({
                      ...draft,
                      translation: {
                        ...draft.translation,
                        providers: {
                          ...draft.translation.providers,
                          local: {
                            ...draft.translation.providers.local,
                            selected_model: id,
                          },
                        },
                      },
                    })
                  }
                />
              ) : page === "tts" || page === "clone" ? (
                <VoiceLibrary key={page} clone={page === "clone"} />
              ) : page === "performance" ? (
                <PerformancePage draft={draft} setDraft={setDraft} />
              ) : page === "general" ? (
                <GeneralPage draft={draft} setDraft={setDraft} />
              ) : (
                <StaticPage page={page} />
              )
            ) : null}
          </main>
          <footer className="flex min-h-12 items-center gap-2 border-t px-4">
            <p className="mr-auto max-w-[55%] truncate text-[9px] text-muted-foreground">
              {message ??
                (loadError
                  ? "Settings failed to load"
                  : "Application-level settings")}
            </p>
            <Button
              variant="outline"
              size="sm"
              className="h-7 text-[11px]"
              onClick={() => onOpenChange(false)}
            >
              Cancel
            </Button>
            <Button
              size="sm"
              className="h-7 text-[11px]"
              disabled={!draft || busy !== null || loadError !== null}
              onClick={() => void save()}
            >
              {busy === "save" && <Loader2 className="animate-spin" />}Save
              Changes
            </Button>
          </footer>
        </div>
      </section>
    </div>
  );
}

function LoadError({ error, retry }: { error: string; retry: () => void }) {
  return (
    <div className="grid h-full place-items-center">
      <div
        role="alert"
        className="max-w-md rounded-lg border border-destructive/30 bg-destructive/5 p-4"
      >
        <div className="flex items-start gap-2">
          <AlertCircle className="mt-0.5 size-4 shrink-0 text-destructive" />
          <div>
            <p className="text-xs font-medium">មិនអាចផ្ទុកការកំណត់បាន</p>
            <p className="mt-1 break-words text-[10px] text-muted-foreground">
              {error}
            </p>
            <Button
              variant="outline"
              size="sm"
              className="mt-3 h-7 text-[10px]"
              onClick={retry}
            >
              ព្យាយាមម្ដងទៀត
            </Button>
          </div>
        </div>
      </div>
    </div>
  );
}

function ModelsPage({
  models,
  selectedModel,
  busy,
  modelActionId,
  onInstall,
  onRemove,
  onSelect,
}: {
  models: TranslationModel[];
  selectedModel: string | null;
  busy: string | null;
  modelActionId: string | null;
  onInstall: (id: string) => void;
  onRemove: (id: string) => void;
  onSelect: (id: string) => void;
}) {
  return (
    <div className="mx-auto max-w-2xl space-y-4">
      <Section
        title="Local AI Models"
        description="Download translation and voice models. Downloads continue when Settings is closed."
      >
        <div className="space-y-2">
          {models.map((model) => {
            const active = selectedModel === model.id;
            const acting =
              busy === "model-action" && modelActionId === model.id;
            const downloading = model.install_status === "downloading";
            const cancelling = model.install_status === "cancelling";
            const cancelled = model.install_status === "cancelled";
            const failed = model.install_status === "failed";
            const partial =
              !model.installed && (model.downloaded_bytes ?? 0) > 0;
            const progress = Math.max(
              0,
              Math.min(100, model.download_progress ?? 0),
            );
            return (
              <div
                key={model.id}
                className={`rounded-lg border p-3 ${active ? "border-primary/60 bg-primary/5" : "bg-background/30"}`}
              >
                <div className="flex items-start gap-3">
                  <div className="grid size-8 shrink-0 place-items-center rounded-md bg-primary/10 text-primary">
                    <Database className="size-4" />
                  </div>
                  <div className="min-w-0 flex-1">
                    <div className="flex flex-wrap items-center gap-1.5">
                      <p className="text-[11px] font-semibold">{model.name}</p>
                      {active && (
                        <span className="rounded bg-primary/10 px-1.5 py-0.5 text-[8px] font-medium text-primary">
                          Selected
                        </span>
                      )}
                      {model.installed && (
                        <span className="rounded bg-emerald-500/10 px-1.5 py-0.5 text-[8px] font-medium text-emerald-500">
                          Installed
                        </span>
                      )}
                      {downloading && (
                        <span className="rounded bg-primary/10 px-1.5 py-0.5 text-[8px] font-medium text-primary">
                          Downloading · {progress}%
                        </span>
                      )}
                      {cancelling && (
                        <span className="rounded bg-amber-500/10 px-1.5 py-0.5 text-[8px] font-medium text-amber-500">
                          Cancelling
                        </span>
                      )}
                      {cancelled && (
                        <span className="rounded bg-muted px-1.5 py-0.5 text-[8px] font-medium text-muted-foreground">
                          Paused
                        </span>
                      )}
                      {failed && (
                        <span className="rounded bg-destructive/10 px-1.5 py-0.5 text-[8px] font-medium text-destructive">
                          Failed
                        </span>
                      )}
                    </div>
                    <p className="mt-1 text-[9px] leading-relaxed text-muted-foreground">
                      {model.description}
                    </p>
                    {(downloading || cancelling || partial) && (
                      <div className="mt-2">
                        <div className="mb-1 flex items-center justify-between text-[8px] text-muted-foreground">
                          <span>
                            {formatBytes(model.downloaded_bytes ?? 0)} /{" "}
                            {formatBytes(model.total_bytes ?? 0)}
                          </span>
                          <span>{progress}%</span>
                        </div>
                        <div className="h-1.5 overflow-hidden rounded-full bg-muted">
                          <div
                            className="h-full rounded-full bg-primary transition-[width] duration-500 ease-out"
                            style={{ width: `${progress}%` }}
                          />
                        </div>
                      </div>
                    )}
                    {failed && model.install_error && (
                      <p className="mt-1 text-[8px] text-destructive">
                        {model.install_error}
                      </p>
                    )}
                    <div className="mt-1.5 flex flex-wrap gap-x-3 gap-y-1 text-[8px] text-muted-foreground">
                      <span>
                        {model.approximate_size_mb
                          ? formatSize(model.approximate_size_mb)
                          : "Size unknown"}
                      </span>
                      {model.license && <span>{model.license}</span>}
                      {model.repository && (
                        <span className="truncate">{model.repository}</span>
                      )}
                    </div>
                  </div>
                  <div className="flex shrink-0 gap-1">
                    {model.installed ? (
                      <>
                        <Button
                          size="sm"
                          variant={active ? "secondary" : "outline"}
                          className="h-7 text-[9px]"
                          disabled={
                            busy !== null || active || model.kind === "tts"
                          }
                          onClick={() => onSelect(model.id)}
                        >
                          {active ? <CheckIcon /> : null}
                          {model.kind === "tts"
                            ? "Installed"
                            : active
                              ? "Using"
                              : "Use"}
                        </Button>
                        <Button
                          size="sm"
                          variant="ghost"
                          className="h-7 text-[9px] text-muted-foreground hover:text-destructive"
                          disabled={busy !== null}
                          onClick={() => onRemove(model.id)}
                        >
                          {acting ? (
                            <Loader2 className="animate-spin" />
                          ) : (
                            <Trash2 />
                          )}
                          Remove
                        </Button>
                      </>
                    ) : downloading ? (
                      <Button
                        size="sm"
                        variant="outline"
                        className="h-7 text-[9px] text-destructive"
                        disabled={busy !== null}
                        onClick={() => onRemove(model.id)}
                      >
                        {acting ? <Loader2 className="animate-spin" /> : <X />}
                        Cancel
                      </Button>
                    ) : cancelling ? (
                      <Button
                        size="sm"
                        variant="outline"
                        className="h-7 text-[9px]"
                        disabled
                      >
                        <Loader2 className="animate-spin" />
                        Cancelling
                      </Button>
                    ) : partial ? (
                      <>
                        <Button
                          size="sm"
                          className="h-7 text-[9px]"
                          disabled={busy !== null}
                          onClick={() => onInstall(model.id)}
                        >
                          {acting ? (
                            <Loader2 className="animate-spin" />
                          ) : (
                            <Download />
                          )}
                          Resume
                        </Button>
                        <Button
                          size="sm"
                          variant="ghost"
                          className="h-7 text-[9px] text-muted-foreground hover:text-destructive"
                          disabled={busy !== null}
                          onClick={() => onRemove(model.id)}
                        >
                          <Trash2 />
                          Remove
                        </Button>
                      </>
                    ) : (
                      <Button
                        size="sm"
                        className="h-7 text-[9px]"
                        disabled={busy !== null}
                        onClick={() => onInstall(model.id)}
                      >
                        {acting ? (
                          <Loader2 className="animate-spin" />
                        ) : (
                          <Download />
                        )}
                        {failed ? "Retry" : "Download"}
                      </Button>
                    )}
                  </div>
                </div>
              </div>
            );
          })}
        </div>
        <p className="text-[9px] text-muted-foreground">
          Cancel keeps partial files for Resume. Remove deletes installed or
          partial model data and frees disk space.
        </p>
      </Section>
    </div>
  );
}
function formatSize(mb: number) {
  return mb >= 1024 ? `~${(mb / 1024).toFixed(1)} GB` : `~${mb} MB`;
}
function formatBytes(bytes: number) {
  if (bytes <= 0) return "0 MB";
  const gb = bytes / 1024 / 1024 / 1024;
  return gb >= 1
    ? `${gb.toFixed(2)} GB`
    : `${(bytes / 1024 / 1024).toFixed(0)} MB`;
}

function TranslationPage({
  draft,
  setDraft,
  credential,
  setCredential,
  configured,
  credentialIds,
  models,
  localModels,
  busy,
  refreshModels,
  testConnection,
  addCredential,
  removeCredential,
}: {
  draft: AppSettings;
  setDraft: (v: AppSettings) => void;
  credential: string;
  setCredential: (v: string) => void;
  configured: boolean;
  credentialIds: string[];
  models: TranslationModel[];
  localModels: TranslationModel[];
  busy: string | null;
  refreshModels: () => Promise<void>;
  testConnection: () => Promise<void>;
  addCredential: () => Promise<void>;
  removeCredential: (id: string) => Promise<void>;
}) {
  const provider = draft.translation.provider;
  const config = draft.translation.providers[provider];
  const selectedModel = config.selected_model ?? undefined;
  const patch = (p: Partial<AppSettings["translation"]>) =>
    setDraft({ ...draft, translation: { ...draft.translation, ...p } });
  const patchProvider = (p: Record<string, unknown>) =>
    setDraft({
      ...draft,
      translation: {
        ...draft.translation,
        providers: {
          ...draft.translation.providers,
          [provider]: { ...config, ...p },
        },
      },
    });
  const installedLocal = localModels.filter(
    (model) => model.installed && model.kind !== "tts",
  );
  const localModelItems = installedLocal.map((model) => ({
    label: model.name,
    value: model.id,
  }));
  const geminiModelItems = [
    ...(selectedModel && !models.some((model) => model.id === selectedModel)
      ? [{ label: `${selectedModel} (saved)`, value: selectedModel }]
      : []),
    ...models.map((model) => ({ label: model.name, value: model.id })),
  ];
  return (
    <div className="mx-auto max-w-2xl space-y-4">
      <Section
        title="Translation provider"
        description="ជ្រើស Local ឥតគិតថ្លៃ ឬ Cloud/AI សម្រាប់គុណភាពខ្ពស់។"
      >
        <div className="grid grid-cols-2 gap-2">
          {providers.map((id) => (
            <button
              key={id}
              onClick={() => {
                patch({ provider: id });
                setCredential("");
              }}
              className={`rounded-lg border p-3 text-left ${provider === id ? "border-primary bg-primary/8" : "hover:bg-muted/50"}`}
            >
              <span className="text-xs font-medium">{providerLabels[id]}</span>
              <p className="mt-1 text-[9px] text-muted-foreground">
                {id === "local"
                  ? "Free · Offline"
                  : id === "gemini"
                    ? "Context-aware · Dynamic models"
                    : "Provider-ready"}
              </p>
            </button>
          ))}
        </div>
      </Section>
      {provider === "local" ? (
        <Section
          title="Local translation"
          description="Uses an installed model completely offline."
        >
          <Field label="Model">
            <Select
              value={selectedModel}
              items={localModelItems}
              onValueChange={(value) =>
                patchProvider({ selected_model: value || null })
              }
            >
              <SelectTrigger className="w-full text-xs">
                <SelectValue
                  placeholder={
                    installedLocal.length
                      ? "Select installed model"
                      : "Download a model in Settings → Models"
                  }
                />
              </SelectTrigger>
              <SelectContent align="start">
                <SelectGroup>
                  {localModelItems.map((item) => (
                    <SelectItem key={item.value} value={item.value}>
                      {item.label}
                    </SelectItem>
                  ))}
                </SelectGroup>
              </SelectContent>
            </Select>
          </Field>
          {installedLocal.length === 0 && (
            <p className="text-[9px] text-muted-foreground">
              មិនទាន់មាន local model។ ចូល Models ដើម្បី Download មុន។
            </p>
          )}
        </Section>
      ) : (
        <Section
          title={`${providerLabels[provider]} API keys`}
          description="Keys are stored securely in the OS keychain. Catty rotates automatically when a key is rate-limited."
        >
          {provider === "openai_compatible" && (
            <Field label="Base URL">
              <Input
                value={draft.translation.providers.openai_compatible.base_url}
                onChange={(e) => patchProvider({ base_url: e.target.value })}
                className="h-8 text-xs"
              />
            </Field>
          )}
          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-[11px] font-medium">Saved API keys</p>
                <p className="text-[9px] text-muted-foreground">
                  {credentialIds.length} configured · secrets are never
                  displayed
                </p>
              </div>
              <span
                className={`rounded-full px-2 py-0.5 text-[9px] ${configured ? "bg-emerald-500/10 text-emerald-500" : "bg-muted text-muted-foreground"}`}
              >
                {configured ? "Ready" : "Not configured"}
              </span>
            </div>
            {credentialIds.length > 0 ? (
              <div className="overflow-hidden rounded-md border">
                {credentialIds.map((id, index) => (
                  <div
                    key={id}
                    className="flex h-9 items-center gap-2 border-b px-2 last:border-b-0"
                  >
                    <KeyRound className="size-3.5 text-primary" />
                    <div className="min-w-0 flex-1">
                      <p className="truncate text-[10px] font-medium">
                        API Key {index + 1}
                      </p>
                      <p className="truncate text-[8px] text-muted-foreground">
                        {id === "default"
                          ? "Existing key · primary fallback"
                          : `Secure ID · ${id}`}
                      </p>
                    </div>
                    <Button
                      variant="ghost"
                      size="icon-xs"
                      disabled={busy !== null}
                      className="text-muted-foreground hover:text-destructive"
                      onClick={() => void removeCredential(id)}
                    >
                      <Trash2 />
                    </Button>
                  </div>
                ))}
              </div>
            ) : (
              <div className="rounded-md border border-dashed p-3 text-center text-[9px] text-muted-foreground">
                មិនទាន់មាន API key។ Add one below.
              </div>
            )}
            <div className="flex gap-2">
              <Input
                type="password"
                value={credential}
                onChange={(e) => setCredential(e.target.value)}
                placeholder="Paste a new API key"
                className="h-8 min-w-0 flex-1 text-xs"
              />
              <Button
                size="sm"
                className="h-8 text-[10px]"
                disabled={busy !== null || !credential.trim()}
                onClick={() => void addCredential()}
              >
                {busy === "credential" ? (
                  <Loader2 className="animate-spin" />
                ) : (
                  <Plus />
                )}
                Add Key
              </Button>
            </div>
            <p className="text-[9px] text-muted-foreground">
              When a provider returns 429, Catty temporarily cools that key down
              and tries the next available key.
            </p>
          </div>
          {provider === "gemini" ? (
            <Field label="Model">
              <div className="flex gap-2">
                <Select
                  value={selectedModel}
                  items={geminiModelItems}
                  onValueChange={(value) =>
                    patchProvider({ selected_model: value || null })
                  }
                >
                  <SelectTrigger className="min-w-0 flex-1 text-xs">
                    <SelectValue placeholder="Select Gemini model" />
                  </SelectTrigger>
                  <SelectContent align="start">
                    <SelectGroup>
                      {geminiModelItems.map((item) => (
                        <SelectItem key={item.value} value={item.value}>
                          {item.label}
                        </SelectItem>
                      ))}
                    </SelectGroup>
                  </SelectContent>
                </Select>
                <Button
                  variant="outline"
                  size="sm"
                  className="h-8 text-[10px]"
                  disabled={busy !== null || !configured}
                  onClick={() => void refreshModels()}
                >
                  {busy === "models" && <Loader2 className="animate-spin" />}
                  Refresh Models
                </Button>
              </div>
            </Field>
          ) : (
            <Field label="Model">
              <Input
                value={config.selected_model ?? ""}
                onChange={(e) =>
                  patchProvider({ selected_model: e.target.value || null })
                }
                className="h-8 text-xs"
              />
            </Field>
          )}
          <Button
            variant="outline"
            size="sm"
            className="h-8 text-[10px]"
            disabled={busy !== null || (!configured && !credential.trim())}
            onClick={() => void testConnection()}
          >
            {busy === "test" && <Loader2 className="animate-spin" />}Test
            Connection
          </Button>
        </Section>
      )}
      <Section
        title="Dubbing translation"
        description="Chinese drama → natural spoken Khmer defaults."
      >
        <Field label="Target language">
          <Select
            value={draft.translation.target_language}
            items={targetLanguageItems}
            onValueChange={(value) => {
              if (value) patch({ target_language: value });
            }}
          >
            <SelectTrigger className="w-full text-xs">
              <SelectValue />
            </SelectTrigger>
            <SelectContent align="start">
              <SelectGroup>
                {targetLanguageItems.map((item) => (
                  <SelectItem key={item.value} value={item.value}>
                    {item.label}
                  </SelectItem>
                ))}
              </SelectGroup>
            </SelectContent>
          </Select>
        </Field>
        <Field label="Style">
          <Select
            value={draft.translation.style}
            items={translationStyleItems}
            onValueChange={(value) => {
              if (value) patch({ style: value as TranslationStyle });
            }}
          >
            <SelectTrigger className="w-full text-xs">
              <SelectValue />
            </SelectTrigger>
            <SelectContent align="start">
              <SelectGroup>
                {translationStyleItems.map((item) => (
                  <SelectItem key={item.value} value={item.value}>
                    {item.label}
                  </SelectItem>
                ))}
              </SelectGroup>
            </SelectContent>
          </Select>
        </Field>
        <Check
          label="Use surrounding dialogue context"
          checked={draft.translation.use_context}
          onChange={(v) => patch({ use_context: v })}
        />
        <Check
          label="Use speaker information"
          checked={draft.translation.use_speaker_context}
          onChange={(v) => patch({ use_speaker_context: v })}
        />
      </Section>
    </div>
  );
}

function GeneralPage({
  draft,
  setDraft,
}: {
  draft: AppSettings;
  setDraft: (v: AppSettings) => void;
}) {
  return (
    <div className="mx-auto max-w-2xl space-y-4">
      <Section
        title="Language"
        description="Khmer is the primary interface language."
      >
        <Select
          value={draft.general.language}
          items={languageItems}
          onValueChange={(value) => {
            if (value)
              setDraft({
                ...draft,
                general: { ...draft.general, language: value },
              });
          }}
        >
          <SelectTrigger className="w-full text-xs">
            <SelectValue />
          </SelectTrigger>
          <SelectContent align="start">
            <SelectGroup>
              {languageItems.map((item) => (
                <SelectItem key={item.value} value={item.value}>
                  {item.label}
                </SelectItem>
              ))}
            </SelectGroup>
          </SelectContent>
        </Select>
      </Section>
      <Section title="Editor">
        <Check
          label="Follow playhead while previewing"
          checked={draft.general.follow_playhead}
          onChange={(v) =>
            setDraft({
              ...draft,
              general: { ...draft.general, follow_playhead: v },
            })
          }
        />
      </Section>
    </div>
  );
}
function PerformancePage({
  draft,
  setDraft,
}: {
  draft: AppSettings;
  setDraft: (v: AppSettings) => void;
}) {
  const device = draft.performance.device;
  return (
    <div className="mx-auto max-w-2xl">
      <Section
        title="Compute device"
        description="Auto keeps Mac M1 on a stable path and uses CUDA where supported."
      >
        <Select
          value={device}
          items={computeDeviceItems}
          onValueChange={(value) => {
            if (value)
              setDraft({
                ...draft,
                performance: {
                  ...draft.performance,
                  device: value as ComputeDevice,
                },
              });
          }}
        >
          <SelectTrigger className="w-full text-xs">
            <SelectValue />
          </SelectTrigger>
          <SelectContent align="start">
            <SelectGroup>
              {computeDeviceItems.map((item) => (
                <SelectItem key={item.value} value={item.value}>
                  {item.label}
                </SelectItem>
              ))}
            </SelectGroup>
          </SelectContent>
        </Select>
      </Section>
    </div>
  );
}
function StaticPage({ page }: { page: PageId }) {
  const copy: Record<string, [string, string]> = {
    storage: ["ទីតាំងផ្ទុក", "Projects, models, cache and export locations."],
    shortcuts: [
      "Keyboard Shortcuts",
      "Compact editor shortcuts will be configurable here.",
    ],
    about: ["Catty Dubber Pro", "Local-first AI dubbing studio · v0.1.0"],
  };
  const [title, text] = copy[page] ?? ["Settings", "Coming soon."];
  return (
    <div className="mx-auto max-w-2xl">
      <Section title={title}>
        <p className="text-[10px] text-muted-foreground">{text}</p>
      </Section>
    </div>
  );
}
function Section({
  title,
  description,
  children,
}: {
  title: string;
  description?: string;
  children: ReactNode;
}) {
  return (
    <section className="rounded-lg border bg-card/30 p-3">
      <h3 className="text-xs font-semibold">{title}</h3>
      {description && (
        <p className="mt-0.5 text-[9px] text-muted-foreground">{description}</p>
      )}
      <div className="mt-3 space-y-3">{children}</div>
    </section>
  );
}
function Field({ label, children }: { label: string; children: ReactNode }) {
  return (
    <label className="block">
      <span className="mb-1 block text-[10px] font-medium">{label}</span>
      {children}
    </label>
  );
}
function Check({
  label,
  checked,
  onChange,
}: {
  label: string;
  checked: boolean;
  onChange: (value: boolean) => void;
}) {
  return (
    <label className="flex items-center justify-between gap-4 rounded-md border px-3 py-2">
      <span className="text-[10px]">{label}</span>
      <input
        type="checkbox"
        checked={checked}
        onChange={(e) => onChange(e.target.checked)}
        className="size-3.5 accent-primary"
      />
    </label>
  );
}
