import { useState } from "react";

import { Button } from "@/components/ui/button";

export function DialogueTextEditor({
  text,
  busy,
  onSave,
  onCancel,
}: {
  text: string;
  busy: boolean;
  onSave: (text: string) => Promise<boolean | undefined>;
  onCancel: () => void;
}) {
  const [draft, setDraft] = useState(text);
  const dirty = draft.trim() !== text;
  const save = async () => {
    if (busy || !draft.trim() || !dirty) return;
    if (await onSave(draft)) onCancel();
  };
  return (
    <div className="flex shrink-0 flex-col gap-2 border-t bg-card p-2">
      <label htmlFor="dialogue-source-text" className="text-[10px] font-medium">
        Edit Chinese dialogue
      </label>
      <textarea
        id="dialogue-source-text"
        autoFocus
        lang="zh"
        value={draft}
        maxLength={100000}
        disabled={busy}
        rows={3}
        className="min-h-20 w-full resize-y rounded-md border bg-background px-2 py-1.5 text-xs outline-none focus-visible:ring-1 focus-visible:ring-ring"
        onChange={(event) => setDraft(event.currentTarget.value)}
        onKeyDown={(event) => {
          if (event.nativeEvent.isComposing) return;
          if (event.key === "Escape" && !busy) {
            event.preventDefault();
            onCancel();
          }
          if ((event.metaKey || event.ctrlKey) && event.key === "Enter") {
            event.preventDefault();
            void save();
          }
        }}
      />
      <div className="flex items-center justify-between gap-2">
        <span className="text-[9px] text-muted-foreground">
          Ctrl / ⌘ + Enter to save · Esc to cancel
        </span>
        <div className="flex gap-1">
          <Button size="xs" variant="ghost" disabled={busy} onClick={onCancel}>
            Cancel
          </Button>
          <Button
            size="xs"
            disabled={busy || !dirty || !draft.trim()}
            onClick={() => void save()}
          >
            {busy ? "Saving…" : "Save"}
          </Button>
        </div>
      </div>
    </div>
  );
}
