import { useCallback, useMemo, useState } from "react";

import type { PersistedProject } from "@catty/contracts";
import { isTauri } from "@tauri-apps/api/core";
import { open } from "@tauri-apps/plugin-dialog";

import { allowAssetPath, requestEngine } from "@/features/projects/deps/engine";

import type { OpenProject, RecentProject } from "../types";

const RECENTS_KEY = "catty.recent-projects.v1";
const INVALID_DIRECTORY_CHARS = /[<>:"/\\|?*]/g;

function joinPath(parent: string, child: string) {
  const separator = parent.includes("\\") ? "\\" : "/";
  return `${parent.replace(/[\\/]$/, "")}${separator}${child}`;
}

function safeDirectoryName(name: string) {
  const printable = Array.from(name.trim(), (character) =>
    character.charCodeAt(0) < 32 ? "-" : character,
  ).join("");
  return printable.replace(INVALID_DIRECTORY_CHARS, "-").replace(/[. ]+$/, "") || "Catty Project";
}

function loadRecents(): RecentProject[] {
  try {
    const value = JSON.parse(localStorage.getItem(RECENTS_KEY) ?? "[]");
    return Array.isArray(value) ? value.slice(0, 8) : [];
  } catch {
    return [];
  }
}

export function useProject() {
  const [current, setCurrent] = useState<OpenProject | null>(null);
  const [recentProjects, setRecentProjects] = useState<RecentProject[]>(loadRecents);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const remember = useCallback((directory: string, project: PersistedProject) => {
    setRecentProjects((items) => {
      const next = [
        { directory, name: project.name, openedAt: new Date().toISOString() },
        ...items.filter((item) => item.directory !== directory),
      ].slice(0, 8);
      localStorage.setItem(RECENTS_KEY, JSON.stringify(next));
      return next;
    });
  }, []);

  const load = useCallback(
    async (directory: string) => {
      setBusy(true);
      setError(null);
      try {
        const project = await requestEngine("project.open", { project_directory: directory });
        await allowAssetPath(directory);
        setCurrent({ directory, project });
        remember(directory, project);
      } catch (cause) {
        setError(cause instanceof Error ? cause.message : "មិនអាចបើក Project បានទេ។");
      } finally {
        setBusy(false);
      }
    },
    [remember],
  );

  const create = useCallback(
    async (name: string) => {
      if (!isTauri()) {
        setError("ការបង្កើត Project folder ត្រូវដំណើរការក្នុង Catty desktop app។");
        return;
      }
      const parent = await open({
        directory: true,
        multiple: false,
        title: "ជ្រើសទីតាំងរក្សាទុក Project",
      });
      if (!parent || Array.isArray(parent)) return;
      const directory = joinPath(parent, safeDirectoryName(name));
      setBusy(true);
      setError(null);
      try {
        const project = await requestEngine("project.create", {
          project_directory: directory,
          name: name.trim(),
        });
        await allowAssetPath(directory);
        setCurrent({ directory, project });
        remember(directory, project);
      } catch (cause) {
        setError(cause instanceof Error ? cause.message : "មិនអាចបង្កើត Project បានទេ។");
      } finally {
        setBusy(false);
      }
    },
    [remember],
  );

  const chooseAndOpen = useCallback(async () => {
    if (!isTauri()) {
      setError("ការបើក Project folder ត្រូវដំណើរការក្នុង Catty desktop app។");
      return;
    }
    const directory = await open({ directory: true, multiple: false, title: "បើក Catty Project" });
    if (directory && !Array.isArray(directory)) await load(directory);
  }, [load]);

  const close = useCallback(() => setCurrent(null), []);
  const dismissError = useCallback(() => setError(null), []);

  return useMemo(
    () => ({
      current,
      recentProjects,
      busy,
      error,
      create,
      chooseAndOpen,
      openRecent: load,
      close,
      dismissError,
    }),
    [current, recentProjects, busy, error, create, chooseAndOpen, load, close, dismissError],
  );
}
