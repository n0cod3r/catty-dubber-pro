import { useEffect, useReducer, useState } from "react";

import { EditorPanels } from "@/components/editor/editor-panels";
import { DialoguePanel } from "@/components/workspace/dialogue-panel";
import { Timeline } from "@/components/workspace/timeline";
import { VideoPreview } from "@/components/workspace/video-preview";
import type { EpisodeMedia } from "@/features/episodes/types";
import { useMediaVisuals } from "@/features/media-visuals/use-media-visuals";
import { usePlayback } from "@/features/playback/use-playback";
import { createTimeline, timelineReducer } from "@/features/timeline/model";

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

// A new episode mounts a fresh session: playback, clip edits, mute, and markers
// cannot leak from a previous source, including pending seek requests.
export function EditorWorkspace({
  episode,
  importing,
  onImport,
  followPlayhead,
  onMetadata,
}: EditorWorkspaceProps) {
  const playback = usePlayback();
  const [muted, setMuted] = useState(false);
  const [history, dispatch] = useReducer(timelineReducer, undefined, createTimeline);
  const visuals = useMediaVisuals(episode);
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
          visuals={visuals}
        />
      }
    >
      <VideoPreview
        episode={episode}
        document={history.present}
        currentTime={playback.currentTime}
        seekRequest={playback.seekRequest}
        onSeek={playback.seek}
        onTimeChange={playback.setCurrentTime}
        muted={muted}
        onMuteChange={setMuted}
        onImport={onImport}
        importing={importing}
        onMetadata={(metadata) => {
          if (episode) {
            playback.setDuration(metadata.durationSeconds ?? 0);
            onMetadata(episode.id, metadata);
          }
        }}
      />
      <DialoguePanel episode={episode} />
    </EditorPanels>
  );
}
