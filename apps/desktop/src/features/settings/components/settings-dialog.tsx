import { useMemo, useState } from "react";

import {
  AudioLines,
  Bot,
  Cpu,
  Database,
  Gauge,
  HardDrive,
  Info,
  Keyboard,
  Languages,
  Search,
  Settings2,
  Sparkles,
  X,
} from "lucide-react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

const pages = [
  { id: "general", label: "ទូទៅ", hint: "General", icon: Settings2 },
  { id: "translation", label: "ការបកប្រែ", hint: "Translation", icon: Languages },
  { id: "models", label: "ម៉ូដែល", hint: "Models", icon: Database },
  { id: "tts", label: "សំឡេង & TTS", hint: "Voices & TTS", icon: AudioLines },
  { id: "clone", label: "ចម្លងសំឡេង", hint: "Voice Clone", icon: Bot },
  { id: "performance", label: "ដំណើរការ", hint: "Performance", icon: Gauge },
  { id: "storage", label: "ទីតាំងផ្ទុក", hint: "Storage", icon: HardDrive },
  { id: "shortcuts", label: "ផ្លូវកាត់", hint: "Shortcuts", icon: Keyboard },
  { id: "about", label: "អំពី Catty", hint: "About", icon: Info },
] as const;

type PageId = (typeof pages)[number]["id"];
type TranslationProvider = "local" | "gemini" | "deepseek" | "google" | "baidu" | "custom";

type SettingsDialogProps = { open: boolean; onOpenChange: (open: boolean) => void };

const providers: Array<{ id: TranslationProvider; name: string; note: string; badge?: string }> = [
  { id: "local", name: "Local", note: "ឥតគិតថ្លៃ · Offline · រក្សាឯកជនភាព", badge: "FREE" },
  { id: "gemini", name: "Gemini", note: "Context-aware · គុណភាពខ្ពស់", badge: "AI" },
  { id: "deepseek", name: "DeepSeek", note: "Context-aware · Cloud AI", badge: "AI" },
  { id: "google", name: "Google Cloud", note: "លឿន · Standard translation" },
  { id: "baidu", name: "Baidu", note: "Cloud translation · Chinese-focused" },
  { id: "custom", name: "OpenAI-compatible", note: "Custom endpoint & model" },
];

export function SettingsDialog({ open, onOpenChange }: SettingsDialogProps) {
  const [page, setPage] = useState<PageId>("translation");
  const [query, setQuery] = useState("");
  const [provider, setProvider] = useState<TranslationProvider>("local");
  const [geminiModel, setGeminiModel] = useState("");
  const [apiKey, setApiKey] = useState("");
  const [baseUrl, setBaseUrl] = useState("");
  const filteredPages = useMemo(() => {
    const needle = query.trim().toLowerCase();
    if (!needle) return pages;
    return pages.filter((item) => `${item.label} ${item.hint}`.toLowerCase().includes(needle));
  }, [query]);

  if (!open) return null;

  const selected = pages.find((item) => item.id === page) ?? pages[0];
  return (
    <div className="fixed inset-0 z-[100] grid place-items-center bg-black/45 p-4 backdrop-blur-[2px]" onMouseDown={() => onOpenChange(false)}>
      <section
        role="dialog"
        aria-modal="true"
        aria-label="Catty Settings"
        onMouseDown={(event) => event.stopPropagation()}
        className="flex h-[min(720px,90vh)] w-[min(940px,94vw)] min-h-[520px] overflow-hidden rounded-xl border bg-background shadow-2xl"
      >
        <aside className="flex w-56 shrink-0 flex-col border-r bg-muted/20">
          <div className="flex h-12 items-center gap-2 border-b px-3">
            <div className="grid size-7 place-items-center rounded-md bg-primary/15 text-primary"><Settings2 className="size-4" /></div>
            <div className="min-w-0"><p className="text-xs font-semibold">ការកំណត់</p><p className="text-[9px] text-muted-foreground">Catty Dubber Pro</p></div>
          </div>
          <div className="p-2">
            <div className="relative"><Search className="absolute left-2 top-1/2 size-3.5 -translate-y-1/2 text-muted-foreground" /><Input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="ស្វែងរក..." className="h-8 pl-7 text-xs" /></div>
          </div>
          <nav className="min-h-0 flex-1 overflow-auto px-2 pb-2">
            {filteredPages.map(({ id, label, hint, icon: Icon }) => (
              <button key={id} type="button" onClick={() => setPage(id)} className={`mb-0.5 flex w-full items-center gap-2 rounded-md px-2 py-1.5 text-left transition-colors ${page === id ? "bg-primary/12 text-primary" : "text-muted-foreground hover:bg-muted hover:text-foreground"}`}>
                <Icon className="size-3.5 shrink-0" /><span className="min-w-0"><span className="block text-[11px] font-medium text-foreground">{label}</span><span className="block truncate text-[9px]">{hint}</span></span>
              </button>
            ))}
          </nav>
          <div className="border-t px-3 py-2 text-[9px] text-muted-foreground">Khmer-first · Local-first</div>
        </aside>

        <div className="flex min-w-0 flex-1 flex-col">
          <header className="flex h-12 shrink-0 items-center border-b px-4">
            <div><h2 className="text-sm font-semibold">{selected.label}</h2><p className="text-[10px] text-muted-foreground">{selected.hint}</p></div>
            <Button variant="ghost" size="icon-xs" className="ml-auto" aria-label="បិទ Settings" onClick={() => onOpenChange(false)}><X /></Button>
          </header>
          <div className="min-h-0 flex-1 overflow-auto p-4">
            {page === "translation" ? (
              <TranslationSettings provider={provider} setProvider={setProvider} apiKey={apiKey} setApiKey={setApiKey} geminiModel={geminiModel} setGeminiModel={setGeminiModel} baseUrl={baseUrl} setBaseUrl={setBaseUrl} />
            ) : page === "models" ? (
              <ModelsSettings />
            ) : page === "performance" ? (
              <PerformanceSettings />
            ) : page === "shortcuts" ? (
              <ShortcutsSettings />
            ) : (
              <PlaceholderPage page={page} />
            )}
          </div>
          <footer className="flex h-12 shrink-0 items-center border-t px-4">
            <p className="text-[9px] text-muted-foreground">Settings persistence & provider connections are the next wiring step.</p>
            <Button variant="outline" size="sm" className="ml-auto h-7 text-[11px]" onClick={() => onOpenChange(false)}>បិទ</Button>
          </footer>
        </div>
      </section>
    </div>
  );
}

function TranslationSettings({ provider, setProvider, apiKey, setApiKey, geminiModel, setGeminiModel, baseUrl, setBaseUrl }: { provider: TranslationProvider; setProvider: (value: TranslationProvider) => void; apiKey: string; setApiKey: (value: string) => void; geminiModel: string; setGeminiModel: (value: string) => void; baseUrl: string; setBaseUrl: (value: string) => void }) {
  const cloud = provider !== "local";
  return <div className="mx-auto max-w-2xl space-y-4">
    <Section title="Translation provider" description="ជ្រើសរើសរវាង Local ឥតគិតថ្លៃ និង Cloud/AI ដែលមានគុណភាពខ្ពស់។">
      <div className="grid grid-cols-2 gap-2">
        {providers.map((item) => <button key={item.id} type="button" onClick={() => setProvider(item.id)} className={`rounded-lg border p-3 text-left transition-colors ${provider === item.id ? "border-primary bg-primary/8" : "hover:bg-muted/50"}`}><div className="flex items-center gap-2"><span className="text-xs font-medium">{item.name}</span>{item.badge && <span className="rounded bg-primary/10 px-1.5 py-0.5 text-[8px] font-semibold text-primary">{item.badge}</span>}{provider === item.id && <span className="ml-auto size-1.5 rounded-full bg-primary" />}</div><p className="mt-1 text-[9px] text-muted-foreground">{item.note}</p></button>)}
      </div>
    </Section>
    {provider === "local" ? <Section title="Local translation" description="ប្រើម៉ូដែលដែលបានដំឡើងក្នុងម៉ាស៊ីន។ មិនត្រូវការ API key។"><Field label="Model"><select className="h-8 w-full rounded-md border bg-background px-2 text-xs"><option>មិនទាន់មាន Local translation model</option></select></Field><div className="rounded-md border border-dashed p-3 text-[10px] text-muted-foreground">ទៅកាន់ទំព័រ Models ដើម្បី download/install ម៉ូដែល Chinese → Khmer។</div></Section> : <Section title={`${providers.find((item) => item.id === provider)?.name ?? "Cloud"} connection`} description="Credentials ជា app-level secret ហើយមិនគួររក្សាទុកក្នុង project.json។">{provider === "custom" && <Field label="Base URL"><Input value={baseUrl} onChange={(e) => setBaseUrl(e.target.value)} placeholder="https://api.example.com/v1" className="h-8 text-xs" /></Field>}<Field label="API Key"><Input type="password" value={apiKey} onChange={(e) => setApiKey(e.target.value)} placeholder="••••••••••••••••" className="h-8 text-xs" /></Field>{provider === "gemini" ? <Field label="Model"><div className="flex gap-2"><select value={geminiModel} onChange={(e) => setGeminiModel(e.target.value)} className="h-8 min-w-0 flex-1 rounded-md border bg-background px-2 text-xs"><option value="">Select Gemini model</option></select><Button variant="outline" size="sm" className="h-8 text-[10px]">Refresh Models</Button></div></Field> : <Field label="Model"><Input placeholder="Provider model" className="h-8 text-xs" /></Field>}<Button variant="outline" size="sm" className="h-8 text-[10px]" disabled={!apiKey || (provider === "custom" && !baseUrl)}>Test Connection</Button></Section>}
    <Section title="Dubbing translation" description="Default behavior for Chinese drama → natural spoken Khmer."><Field label="Target language"><select className="h-8 w-full rounded-md border bg-background px-2 text-xs"><option>ខ្មែរ (Khmer)</option></select></Field><Field label="Style"><select className="h-8 w-full rounded-md border bg-background px-2 text-xs"><option>Natural Dubbing</option><option>Accurate / Literal</option><option>Short & Conversational</option></select></Field><Toggle label="Use surrounding dialogue context" defaultChecked /><Toggle label="Use speaker information" defaultChecked /><Toggle label="Consider dialogue duration" defaultChecked /></Section>
    {cloud && <p className="text-[9px] text-muted-foreground">Cloud providers may charge based on their own pricing. Catty will show provider/model details before translation.</p>}
  </div>;
}

function ModelsSettings() { return <div className="mx-auto max-w-2xl space-y-4"><Section title="Smart Transcribe" description="Models used by the current Chinese transcription pipeline."><ModelRow name="Paraformer + FSMN-VAD + CT-Punc + CAM++" detail="Chinese ASR · punctuation · speaker detection" status="Managed automatically" /></Section><Section title="Local Translation" description="Offline Chinese → Khmer translation models."><ModelRow name="Chinese → Khmer" detail="Free · Offline · Local processing" status="Not installed" action="Download" /></Section><Section title="Voice Clone" description="Local voice cloning models."><ModelRow name="VoxCPM2" detail="Voice cloning · planned dubbing provider" status="Not installed" action="Download" /></Section></div>; }
function PerformanceSettings() { return <div className="mx-auto max-w-2xl"><Section title="Compute device" description="Catty auto-selects a safe runtime for the current machine."><Field label="Device"><select className="h-8 w-full rounded-md border bg-background px-2 text-xs"><option>Auto (recommended)</option><option>CPU</option><option>CUDA</option><option>MPS</option></select></Field><Field label="CPU threads"><Input type="number" placeholder="Auto" className="h-8 text-xs" /></Field></Section></div>; }
function ShortcutsSettings() { return <div className="mx-auto max-w-2xl"><Section title="Editor shortcuts" description="Keyboard controls available in the editor.">{[["Play / pause", "Space"],["Seek 1/30 second", "← / →"],["Seek five seconds", "Shift + ← / →"],["Toggle sidebar", "⌘ / Ctrl + B"]].map(([label,key]) => <div key={label} className="flex items-center justify-between border-b py-2 text-[11px] last:border-0"><span>{label}</span><kbd>{key}</kbd></div>)}</Section></div>; }
function PlaceholderPage({ page }: { page: PageId }) { const copy: Record<string, [string,string]> = { general:["General settings","Language, startup and workspace defaults will live here."], tts:["Voices & TTS","Edge TTS and future voice providers will be configured here."], clone:["Voice Clone","VoxCPM2 and reference-audio defaults will be configured here."], storage:["Storage","Model, cache, project and export locations will be managed here."], about:["Catty Dubber Pro","Version, engine, FFmpeg and update information will live here."] }; const [title, description] = copy[page] ?? ["Settings","Configuration coming soon."]; return <div className="mx-auto max-w-2xl"><Section title={title} description={description}><div className="grid min-h-36 place-items-center rounded-md border border-dashed text-[10px] text-muted-foreground"><Sparkles className="mb-2 size-5 text-primary/60" /></div></Section></div>; }
function Section({ title, description, children }: { title: string; description: string; children: React.ReactNode }) { return <section className="rounded-lg border bg-card/30 p-3"><h3 className="text-xs font-semibold">{title}</h3><p className="mt-0.5 mb-3 text-[9px] leading-relaxed text-muted-foreground">{description}</p><div className="space-y-3">{children}</div></section>; }
function Field({ label, children }: { label: string; children: React.ReactNode }) { return <label className="grid gap-1.5"><span className="text-[10px] font-medium">{label}</span>{children}</label>; }
function Toggle({ label, defaultChecked }: { label: string; defaultChecked?: boolean }) { return <label className="flex items-center justify-between gap-3 py-1 text-[10px]"><span>{label}</span><input type="checkbox" defaultChecked={defaultChecked} className="accent-primary" /></label>; }
function ModelRow({ name, detail, status, action }: { name: string; detail: string; status: string; action?: string }) { return <div className="flex items-center gap-3 rounded-md border p-2.5"><div className="grid size-8 shrink-0 place-items-center rounded-md bg-primary/10 text-primary"><Cpu className="size-4" /></div><div className="min-w-0 flex-1"><p className="truncate text-[11px] font-medium">{name}</p><p className="text-[9px] text-muted-foreground">{detail}</p><p className="mt-1 text-[9px] text-primary">{status}</p></div>{action && <Button variant="outline" size="sm" className="h-7 text-[9px]">{action}</Button>}</div>; }
