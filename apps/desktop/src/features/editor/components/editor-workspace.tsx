import { useEffect, useReducer, useState } from "react";

import type { EpisodeMedia } from "@/features/editor/deps/episodes";
import { usePlayback } from "@/features/editor/deps/playback";
import { VideoPreview } from "@/features/editor/deps/preview";
import {
  createTimeline,
  documentDuration,
  Timeline,
  timelineReducer,
} from "@/features/editor/deps/timeline";

import { EditorPanels } from "./editor-panels";
import { Inspector } from "./inspector";

type EditorWorkspaceProps = {
  episode: EpisodeMedia | null;
  importing: boolean;
  onImport: () => void;
  followPlayhead: boolean;
  onMetadata: (
    id: string,
    metadata: Pick<EpisodeMedia, "durationSeconds" | "width" | "height">,
  ) => void;
};
export function EditorWorkspace({
  episode,
  importing,
  onImport,
  followPlayhead,
  onMetadata,
}: EditorWorkspaceProps) {
  const [muted, setMuted] = useState(false);
  const [history, dispatch] = useReducer(timelineReducer, undefined, createTimeline);
  const duration = documentDuration(history.present);
  const playback = usePlayback(duration);
  const sourceId = episode?.id;
  const sourceName = episode?.name;
  const sourceDuration = episode?.durationSeconds;
  useEffect(() => {
    if (sourceId && sourceName && sourceDuration)
      dispatch({ type: "initialize", sourceId, name: sourceName, duration: sourceDuration });
  }, [sourceId, sourceName, sourceDuration]);
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
          history={history}
          dispatch={dispatch}
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
      inspector={<Inspector episode={episode} />}
    />
  );
}
