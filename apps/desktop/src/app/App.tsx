import { FolderOpen, Mic2, Settings, Sparkles } from "lucide-react";

const workflow = ["Import", "Transcribe", "Translate", "Speakers", "Voices", "Mix", "Export"];

const navItemClass =
  "flex w-full items-center gap-2 rounded-[6px] border-0 bg-transparent px-2 py-[7px] text-left text-xs text-[#aaa29a] transition-colors hover:bg-catty-surface hover:text-catty-text";

export function App() {
  return (
    <div className="grid h-screen grid-cols-[190px_minmax(0,1fr)] overflow-hidden bg-catty-bg text-catty-text">
      <aside className="flex flex-col border-r border-catty-border bg-catty-sidebar px-2.5 py-3.5">
        <div className="flex items-center gap-2.5 px-1.5 pb-4 pt-1">
          <div className="grid size-7 place-items-center rounded-catty-lg bg-catty-accent text-xs font-extrabold text-[#160f0b]">
            C
          </div>
          <div className="leading-none">
            <strong className="block text-[13px] leading-[1.1]">Catty</strong>
            <span className="mt-0.5 block text-[10px] leading-[1.1] text-catty-muted">Dubber Pro</span>
          </div>
        </div>

        <nav className="grid gap-[3px]">
          <button className={`${navItemClass} bg-catty-surface text-catty-text`}>
            <FolderOpen className="text-catty-accent" size={15} /> Project
          </button>
          <button className={navItemClass}>
            <Mic2 size={15} /> Voice Library
          </button>
          <button className={navItemClass}>
            <Settings size={15} /> Settings
          </button>
        </nav>

        <div className="mt-auto px-1.5 pb-0.5 pt-2 text-[9px] text-catty-muted">
          <span className="mr-1.5 inline-block size-1.5 rounded-full bg-catty-success" />
          Engine foundation ready
        </div>
      </aside>

      <main className="grid min-w-0 grid-rows-[auto_auto_1fr_185px]">
        <header className="flex h-[62px] items-center justify-between border-b border-catty-border px-4 py-2.5">
          <div>
            <span className="text-[8px] tracking-[0.12em] text-catty-muted">DUBBING WORKSPACE</span>
            <h1 className="mt-0.5 text-[15px] font-semibold">Untitled project</h1>
          </div>
          <button className="inline-flex items-center gap-1.5 rounded-catty border border-catty-accent-hover bg-catty-accent px-2.5 py-[7px] text-[11px] font-semibold text-[#17100c] transition-colors hover:bg-catty-accent-hover">
            <FolderOpen size={14} /> Import episode
          </button>
        </header>

        <section className="flex min-h-10 items-center gap-1 border-b border-catty-border bg-[#131210] px-4 py-[7px]">
          {workflow.map((item, index) => (
            <div
              className={`flex items-center gap-1.5 rounded-[5px] px-[7px] py-[5px] text-[9px] ${
                index === 0 ? "bg-catty-accent-soft text-[#e7b291]" : "text-[#756f69]"
              }`}
              key={item}
            >
              <span
                className={`grid size-[15px] place-items-center rounded-full border text-[8px] ${
                  index === 0 ? "border-catty-accent" : "border-[#39332e]"
                }`}
              >
                {index + 1}
              </span>
              {item}
            </div>
          ))}
        </section>

        <section className="flex flex-col items-center justify-center p-8 text-center">
          <div className="mb-2.5 grid size-[42px] place-items-center rounded-xl border border-[#4b3529] bg-catty-accent-soft text-catty-accent">
            <Sparkles size={22} />
          </div>
          <h2 className="text-base font-semibold">Catty Dubber Pro</h2>
          <p className="my-2 max-w-[510px] text-[11px] leading-[1.6] text-catty-muted">
            The new desktop shell is running. Import, dubbing engine, timeline and editing tools will be migrated into this workspace without carrying over the old PySide6 interface.
          </p>
          <button className="inline-flex items-center gap-1.5 rounded-catty border border-catty-border bg-catty-surface px-2.5 py-[7px] text-[11px] text-catty-text transition-colors hover:border-[#49413b] hover:bg-[#24201c]">
            <FolderOpen size={14} /> Choose a video
          </button>
        </section>

        <section className="min-h-0 border-t border-catty-border bg-[#12110f]">
          <div className="flex justify-between border-b border-catty-border px-3 py-[7px] text-[9px] text-catty-muted">
            <span>Timeline</span>
            <span>00:00:00 / 00:00:00</span>
          </div>
          {["VIDEO", "DIALOGUE", "KHMER DUB"].map((track) => (
            <div className="grid min-h-[45px] grid-cols-[85px_1fr] border-b border-catty-border-subtle" key={track}>
              <span className="border-r border-catty-border-subtle px-2.5 py-2 text-[8px] text-[#746d67]">{track}</span>
              <div className="m-[7px] rounded border border-dashed border-[#2d2925]" />
            </div>
          ))}
        </section>
      </main>
    </div>
  );
}
