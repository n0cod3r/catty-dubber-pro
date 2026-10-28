import {
  useEffect,
  useMemo,
  useRef,
  useState,
  useSyncExternalStore,
} from "react";
import { createPortal } from "react-dom";

import { FileText, X } from "lucide-react";

import { Button } from "@/components/ui/button";
import {
  Select,
  SelectContent,
  SelectGroup,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";

import {
  clearLogs,
  getLogs,
  pollNativeLogs,
  subscribeLogs,
} from "../services/log-store";

const SOURCE_ITEMS = [
  { label: "All sources", value: "all" },
  { label: "Frontend", value: "frontend" },
  { label: "Rust", value: "rust" },
  { label: "Python", value: "python" },
];

const LEVEL_ITEMS = [
  { label: "All levels", value: "all" },
  ...["DEBUG", "INFO", "WARNING", "WARN", "ERROR"].map((level) => ({
    label: level,
    value: level,
  })),
];

export function LogsButton() {
  const [open, setOpen] = useState(false);
  const trigger = useRef<HTMLButtonElement>(null);
  return (
    <>
      <button
        ref={trigger}
        type="button"
        onClick={() => setOpen(true)}
        className="flex items-center gap-1 rounded px-1.5 py-0.5 hover:bg-muted hover:text-foreground focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
        aria-haspopup="dialog"
      >
        <FileText className="size-3" />
        Logs
      </button>
      {open && (
        <LogsDialog
          onClose={() => {
            setOpen(false);
            requestAnimationFrame(() => trigger.current?.focus());
          }}
        />
      )}
    </>
  );
}
function LogsDialog({ onClose }: { onClose: () => void }) {
  const dialog = useRef<HTMLDialogElement>(null);
  const viewport = useRef<HTMLDivElement>(null);
  const logs = useSyncExternalStore(subscribeLogs, getLogs);
  const [search, setSearch] = useState("");
  const [source, setSource] = useState("all");
  const [level, setLevel] = useState("all");
  const [follow, setFollow] = useState(true);
  const [status, setStatus] = useState("");
  useEffect(() => {
    dialog.current?.showModal();
    let active = true;
    let timer: ReturnType<typeof setTimeout>;
    const poll = async () => {
      try {
        await pollNativeLogs();
      } catch {
        if (active)
          setStatus(
            "Could not read desktop logs. Restart Catty after updating.",
          );
      }
      if (active) timer = setTimeout(() => void poll(), 750);
    };
    void poll();
    return () => {
      active = false;
      clearTimeout(timer);
    };
  }, []);
  const filtered = useMemo(
    () =>
      logs.filter(
        (entry) =>
          (source === "all" || entry.source === source) &&
          (level === "all" || entry.level === level) &&
          `${entry.message} ${entry.source} ${entry.level}`
            .toLowerCase()
            .includes(search.toLowerCase()),
      ),
    [logs, source, level, search],
  );
  useEffect(() => {
    if (follow && viewport.current)
      viewport.current.scrollTop = viewport.current.scrollHeight;
  }, [filtered, follow]);
  const copy = async () => {
    try {
      await navigator.clipboard.writeText(
        filtered
          .map(
            (entry) =>
              `${new Date(entry.timestamp).toISOString()} ${entry.level} ${entry.source} ${entry.message}`,
          )
          .join("\n"),
      );
      setStatus("Copied visible logs");
    } catch {
      setStatus(
        "Clipboard unavailable. Select and copy the log text manually.",
      );
    }
  };
  return createPortal(
    <dialog
      ref={dialog}
      aria-labelledby="logs-title"
      onCancel={onClose}
      onClick={(event) => {
        if (event.target === event.currentTarget) {
          const bounds = event.currentTarget.getBoundingClientRect();
          if (
            event.clientX < bounds.left ||
            event.clientX > bounds.right ||
            event.clientY < bounds.top ||
            event.clientY > bounds.bottom
          )
            onClose();
        }
      }}
      className="fixed inset-0 m-auto h-[min(680px,85dvh)] max-h-[85dvh] w-[min(1100px,94vw)] max-w-[94vw] overflow-hidden rounded-xl border bg-card p-0 text-foreground shadow-2xl backdrop:bg-black/60"
    >
      <div className="flex h-full flex-col">
        <header className="flex items-center gap-2 border-b px-4 py-3">
          <FileText className="size-4 text-primary" />
          <h2 id="logs-title" className="text-sm font-semibold">
            Logs
          </h2>
          <span className="text-[10px] text-muted-foreground">
            Current app session
          </span>
          <Button
            variant="ghost"
            size="icon-xs"
            className="ml-auto"
            aria-label="Close logs"
            onClick={onClose}
          >
            <X />
          </Button>
        </header>
        <div className="flex flex-wrap items-center gap-2 border-b p-3 text-xs">
          <input
            autoFocus
            aria-label="Search logs"
            placeholder="Search logs…"
            value={search}
            onChange={(event) => setSearch(event.target.value)}
            className="min-w-36 flex-1 rounded border bg-background px-2 py-1.5 outline-none focus:ring-1 focus:ring-ring"
          />
          <Select
            value={source}
            items={SOURCE_ITEMS}
            onValueChange={(val) => {
              if (val) setSource(val);
            }}
          >
            <SelectTrigger
              aria-label="Log source"
              className="rounded border bg-background p-1.5"
            >
              <SelectValue placeholder="Select source..." />
            </SelectTrigger>
            <SelectContent container={dialog}>
              <SelectGroup>
                {SOURCE_ITEMS.map((item) => (
                  <SelectItem key={item.value} value={item.value}>
                    {item.label}
                  </SelectItem>
                ))}
              </SelectGroup>
            </SelectContent>
          </Select>
          <Select
            value={level}
            items={LEVEL_ITEMS}
            onValueChange={(val) => {
              if (val) setLevel(val);
            }}
          >
            <SelectTrigger
              aria-label="Log level"
              className="rounded border bg-background p-1.5"
            >
              <SelectValue placeholder="All levels" />
            </SelectTrigger>
            <SelectContent container={dialog}>
              <SelectGroup>
                {LEVEL_ITEMS.map((item) => (
                  <SelectItem key={item.value} value={item.value}>
                    {item.label}
                  </SelectItem>
                ))}
              </SelectGroup>
            </SelectContent>
          </Select>
          <Button variant="outline" onClick={() => void copy()}>
            Copy
          </Button>
          <Button variant="ghost" onClick={clearLogs}>
            Clear
          </Button>
        </div>
        <div
          ref={viewport}
          role="region"
          aria-label="Application logs"
          tabIndex={0}
          className="min-h-0 flex-1 overflow-auto bg-background/50 p-2 font-mono text-[11px] select-text"
        >
          {filtered.length ? (
            filtered.map((entry) => (
              <div
                key={entry.id}
                className="grid grid-cols-[80px_60px_65px_minmax(0,1fr)] gap-2 border-b border-border/40 py-1"
              >
                <span className="text-muted-foreground">
                  {new Date(entry.timestamp).toLocaleTimeString([], {
                    hour12: false,
                  })}
                </span>
                <span
                  className={
                    entry.level === "ERROR"
                      ? "text-destructive"
                      : entry.level.startsWith("WARN")
                        ? "text-amber-500"
                        : "text-muted-foreground"
                  }
                >
                  {entry.level}
                </span>
                <span className="text-primary">{entry.source}</span>
                <pre className="m-0 whitespace-pre-wrap break-words font-inherit">
                  {entry.message}
                </pre>
              </div>
            ))
          ) : (
            <p className="p-6 text-center text-muted-foreground">
              {logs.length
                ? "No matching logs"
                : "No logs yet. App activity will appear here."}
            </p>
          )}
        </div>
        <footer className="flex items-center gap-3 border-t px-3 py-2 text-[10px] text-muted-foreground">
          <span>
            {filtered.length} / {logs.length} entries · latest 2,000
          </span>
          <span role="status" className="min-w-0 flex-1 truncate">
            {status}
          </span>
          <label className="flex items-center gap-1">
            <input
              type="checkbox"
              checked={follow}
              onChange={(event) => setFollow(event.target.checked)}
            />
            Follow
          </label>
        </footer>
      </div>
    </dialog>,
    document.body,
  );
}
