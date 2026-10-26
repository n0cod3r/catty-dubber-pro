import { FolderOpen, Mic2, Settings, Sparkles } from "lucide-react";

const workflow = ["Import", "Transcribe", "Translate", "Speakers", "Voices", "Mix", "Export"];

export function App() {
  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand">
          <div className="brand-mark">C</div>
          <div>
            <strong>Catty</strong>
            <span>Dubber Pro</span>
          </div>
        </div>

        <nav className="nav">
          <button className="nav-item active"><FolderOpen size={15} /> Project</button>
          <button className="nav-item"><Mic2 size={15} /> Voice Library</button>
          <button className="nav-item"><Settings size={15} /> Settings</button>
        </nav>

        <div className="sidebar-footer">
          <span className="status-dot" /> Engine foundation ready
        </div>
      </aside>

      <main className="workspace">
        <header className="topbar">
          <div>
            <span className="eyebrow">DUBBING WORKSPACE</span>
            <h1>Untitled project</h1>
          </div>
          <button className="primary-button"><FolderOpen size={14} /> Import episode</button>
        </header>

        <section className="workflow-bar">
          {workflow.map((item, index) => (
            <div className={index === 0 ? "workflow-step active" : "workflow-step"} key={item}>
              <span>{index + 1}</span>{item}
            </div>
          ))}
        </section>

        <section className="empty-workspace">
          <div className="empty-icon"><Sparkles size={22} /></div>
          <h2>Catty Dubber Pro</h2>
          <p>The new desktop shell is running. Import, dubbing engine, timeline and editing tools will be migrated into this workspace without carrying over the old PySide6 interface.</p>
          <button className="secondary-button"><FolderOpen size={14} /> Choose a video</button>
        </section>

        <section className="timeline-shell">
          <div className="timeline-header"><span>Timeline</span><span>00:00:00 / 00:00:00</span></div>
          <div className="track"><span>VIDEO</span><div /></div>
          <div className="track"><span>DIALOGUE</span><div /></div>
          <div className="track"><span>KHMER DUB</span><div /></div>
        </section>
      </main>
    </div>
  );
}
