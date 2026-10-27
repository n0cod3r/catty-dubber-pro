import { useState } from "react";

import { FolderOpen, LoaderCircle, Plus, Sparkles } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

import type { RecentProject } from "../types";

export function ProjectHome({
  busy,
  error,
  recents,
  onCreate,
  onOpen,
  onOpenRecent,
}: {
  busy: boolean;
  error: string | null;
  recents: RecentProject[];
  onCreate: (name: string) => Promise<void>;
  onOpen: () => Promise<void>;
  onOpenRecent: (directory: string) => Promise<void>;
}) {
  const [name, setName] = useState("");
  const canCreate = name.trim().length > 0 && !busy;

  return (
    <main className="flex h-svh min-h-0 bg-background text-foreground">
      <div className="m-auto w-full max-w-2xl px-6 py-8">
        <div className="mb-7 flex items-center gap-3">
          <div className="flex size-9 items-center justify-center rounded-lg border border-primary/25 bg-primary/10 text-primary">
            <Sparkles className="size-4" />
          </div>
          <div>
            <h1 className="text-base font-semibold tracking-tight">Catty Dubber Pro</h1>
            <p className="text-xs text-muted-foreground">
              ស្ទូឌីយោ dubbing សម្រាប់ការងារលឿន និងរៀបរយ
            </p>
          </div>
        </div>

        <section className="rounded-xl border bg-card p-4 shadow-sm">
          <h2 className="text-sm font-medium">បង្កើត Project ថ្មី</h2>
          <p className="mt-1 text-xs text-muted-foreground">
            Project នឹងរក្សាទុក episodes, audio, transcript, voices និង exports ទាំងអស់នៅក្នុង
            folder មួយ។
          </p>
          <div className="mt-4 flex gap-2">
            <Input
              value={name}
              disabled={busy}
              placeholder="ឧ. Chinese Drama Season 1"
              className="h-8 text-xs"
              onChange={(event) => setName(event.target.value)}
              onKeyDown={(event) => {
                if (event.key === "Enter" && canCreate) void onCreate(name);
              }}
            />
            <Button
              size="sm"
              className="h-8 shrink-0"
              disabled={!canCreate}
              onClick={() => void onCreate(name)}
            >
              {busy ? <LoaderCircle className="animate-spin" /> : <Plus />}
              បង្កើត
            </Button>
          </div>
          <div className="my-4 h-px bg-border" />
          <Button
            variant="outline"
            size="sm"
            className="h-8"
            disabled={busy}
            onClick={() => void onOpen()}
          >
            <FolderOpen /> បើក Project ដែលមានស្រាប់
          </Button>
          {error && (
            <p className="mt-3 rounded-md border border-destructive/25 bg-destructive/10 px-3 py-2 text-xs text-destructive">
              {error}
            </p>
          )}
        </section>

        <section className="mt-5">
          <div className="mb-2 flex items-center justify-between">
            <h2 className="text-xs font-medium text-muted-foreground">Project ថ្មីៗ</h2>
            <span className="text-[11px] text-muted-foreground">{recents.length}</span>
          </div>
          {recents.length === 0 ? (
            <div className="rounded-lg border border-dashed px-4 py-5 text-center text-xs text-muted-foreground">
              មិនទាន់មាន Project ថ្មីៗទេ។
            </div>
          ) : (
            <div className="overflow-hidden rounded-lg border bg-card">
              {recents.map((project) => (
                <button
                  key={project.directory}
                  type="button"
                  disabled={busy}
                  className="flex w-full items-center gap-3 border-b px-3 py-2.5 text-left last:border-b-0 hover:bg-accent/60 disabled:opacity-50"
                  onClick={() => void onOpenRecent(project.directory)}
                >
                  <FolderOpen className="size-4 shrink-0 text-primary" />
                  <span className="min-w-0 flex-1">
                    <span className="block truncate text-xs font-medium">{project.name}</span>
                    <span className="block truncate text-[11px] text-muted-foreground">
                      {project.directory}
                    </span>
                  </span>
                </button>
              ))}
            </div>
          )}
        </section>
      </div>
    </main>
  );
}
