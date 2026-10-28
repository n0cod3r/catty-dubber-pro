import type { PersistedProject } from "@catty/contracts";

export type OpenProject = { directory: string; project: PersistedProject };
export type RecentProject = {
  directory: string;
  name: string;
  openedAt: string;
};
