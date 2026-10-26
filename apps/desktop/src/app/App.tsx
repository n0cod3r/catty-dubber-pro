import { FolderOpen, Mic2, Settings, Sparkles } from "lucide-react";

import { Badge } from "../components/ui/badge";
import { Button } from "../components/ui/button";
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
  return (
    <div className="grid h-screen grid-cols-[190px_minmax(0,1fr)] overflow-hidden bg-catty-bg text-catty-text">
      <aside className="flex flex-col border-r border-catty-border bg-catty-sidebar px-2.5 py-3">
        <div className="flex items-center gap-2.5 px-1.5 pb-3 pt-0.5">
          <div className="grid size-7 place-items-center rounded-catty-lg bg-catty-accent text-xs font-extrabold text-[#160f0b]">C</div>
          <div className="leading-none">
            <strong className="block text-[13px] leading-[1.1]">Catty</strong>
            <span className="mt-0.5 block text-[9px] leading-[1.1] text-catty-muted">Dubber Pro</span>
          </div>
        </div>

        <nav className="grid gap-0.5">
          <NavItem active><FolderOpen className="text-catty-accent" size={14} /> Project</NavItem>
          <NavItem><Mic2 size={14} /> Voice Library</NavItem>
          <NavItem><Settings size={14} /> Settings</NavItem>
        </nav>

        <div className="mt-auto border-t border-catty-border-subtle px-1.5 pb-0.5 pt-2.5">
          <div className="flex items-center gap-1.5 text-[9px] text-catty-muted">
            <span className="size-1.5 rounded-full bg-catty-success" />
            Desktop shell ready
          </div>
        </div>
      </aside>

      <main className="grid min-w-0 grid-rows-[52px_36px_1fr_185px]">
        <header className="flex items-center justify-between border-b border-catty-border px-3.5">
          <div className="min-w-0">
            <div className="flex items-center gap-2">
              <h1 className="truncate text-[13px] font-semibold">Untitled project</h1>
              <Badge>Draft</Badge>
            </div>
            <p className="mt-0.5 text-[9px] text-catty-muted">Dubbing workspace</p>
          </div>
          <Button variant="primary" size="sm"><FolderOpen size={13} /> Import episode</Button>
        </header>

        <section className="flex items-center gap-0.5 overflow-x-auto border-b border-catty-border bg-catty-panel px-3">
          {workflow.map((item, index) => (
            <div
              className={cn(
                "flex h-6 shrink-0 items-center gap-1.5 rounded-catty px-1.5 text-[9px] text-catty-muted-2",
                index === 0 && "bg-catty-accent-soft text-catty-accent-text",
              )}
              key={item}
            >
              <span className={cn("grid size-3.5 place-items-center rounded-full border border-catty-border text-[7px]", index === 0 && "border-catty-accent/60")}>{index + 1}</span>
              {item}
            </div>
          ))}
        </section>

        <section className="flex min-h-0 flex-col items-center justify-center p-6 text-center">
          <div className="mb-2 grid size-9 place-items-center rounded-catty-xl border border-catty-accent/25 bg-catty-accent-soft text-catty-accent"><Sparkles size={18} /></div>
          <h2 className="text-[14px] font-semibold">Start a dubbing project</h2>
          <p className="my-1.5 max-w-[440px] text-[10px] leading-5 text-catty-muted">
            Import an episode to begin transcription, Khmer translation, speaker detection, voice assignment and dubbing.
          </p>
          <Button className="mt-1" size="sm"><FolderOpen size={13} /> Choose video</Button>
        </section>

        <section className="min-h-0 border-t border-catty-border bg-[#12110f]">
          <div className="flex h-7 items-center justify-between border-b border-catty-border px-2.5 text-[9px] text-catty-muted">
            <div className="flex items-center gap-2"><span className="font-medium text-catty-text-soft">Timeline</span><Badge tone="accent">00:00:00</Badge></div>
            <span>00:00:00 / 00:00:00</span>
          </div>
          {["VIDEO", "DIALOGUE", "KHMER DUB"].map((track) => (
            <div className="grid min-h-[45px] grid-cols-[82px_1fr] border-b border-catty-border-subtle" key={track}>
              <span className="border-r border-catty-border-subtle px-2 py-2 text-[8px] font-medium tracking-wide text-catty-muted-2">{track}</span>
              <div className="m-1.5 rounded-catty border border-dashed border-catty-border-subtle bg-catty-panel/20" />
            </div>
          ))}
        </section>
      </main>
    </div>
  );
}
