import { useEffect, useState } from "react";

import type { EpisodeMedia } from "@/features/editor/deps/episodes";
import { usePlayback } from "@/features/editor/deps/playback";
import { VideoPreview } from "@/features/editor/deps/preview";
import {
  documentDuration,
  Timeline,
  TimelineProvider,
  useTimelineStore,
} from "@/features/editor/deps/timeline";

import { EditorPanels } from "./editor-panels";
import { Inspector } from "./inspector";

type EditorWorkspaceProps = {
  episode: EpisodeMedia | null;
  projectDirectory: string;
  importing: boolean;
  onImport: () => void;
  followPlayhead: boolean;
  onMetadata: (
    id: string,
    metadata: Pick<EpisodeMedia, "durationSeconds" | "width" | "height">,
  ) => void;
};
export function EditorWorkspace(props: EditorWorkspaceProps) {
  return (
    <TimelineProvider>
      <WorkspaceContent {...props} />
    </TimelineProvider>
  );
}

function WorkspaceContent({
  episode,
  projectDirectory,
  importing,
  onImport,
  followPlayhead,
  onMetadata,
}: EditorWorkspaceProps) {
  const [muted, setMuted] = useState(false);
  const history = useTimelineStore((state) => state.history);
  const initialize = useTimelineStore((state) => state.initialize);
  const duration = documentDuration(history.present);
  const playback = usePlayback(duration);
  const sourceId = episode?.id;
  const sourceName = episode?.name;
  const sourceDuration = episode?.durationSeconds;
  useEffect(() => {
    if (sourceId && sourceName && sourceDuration)
      initialize({ sourceId, name: sourceName, duration: sourceDuration });
  }, [sourceId, sourceName, sourceDuration, initialize]);
  return (
    <EditorPanels
      timeline={
        <Timeline
          episode={episode}
          currentTime={playback.currentTime}
          onSeek={playback.seek}
          muted={muted}
          onMuteChange={setMuted}
          followPlayhead={followPlayhead}
          duration={duration}
        />
      }
      preview={
        <VideoPreview
          episode={episode}
          document={history.present}
          currentTime={playback.currentTime}
          duration={duration}
          playing={playback.playing}
          onPlayingChange={playback.setPlaying}
          onMediaClock={playback.setMediaClock}
          seekRevision={playback.seekRevision}
          onSeek={playback.seek}
          muted={muted}
          onMuteChange={setMuted}
          onImport={onImport}
          importing={importing}
          onMetadata={(metadata) => {
            if (episode) onMetadata(episode.id, metadata);
          }}
        />
      }
      inspector={<Inspector episode={episode} projectDirectory={projectDirectory} />}
    />
  );
}
