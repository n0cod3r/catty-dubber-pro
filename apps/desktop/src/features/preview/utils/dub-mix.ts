import type { EpisodeMedia } from "../deps/episodes";

export type MixDubClip = {
  id: string;
  start: number;
  duration: number;
  audioPath: string;
  version: string;
};

export function dubMixClips(episode: EpisodeMedia | null): MixDubClip[] {
  if (!episode) return [];
  const segments = new Map(
    (episode.dialogueSegments ?? []).map((segment) => [segment.id, segment]),
  );
  return (episode.dubSegments ?? [])
    .flatMap((dub) => {
      if (dub.status !== "ready" || !dub.audio_path) return [];
      const segment = segments.get(dub.dialogue_segment_id);
      if (!segment) return [];
      const start = Math.max(0, segment.start);
      if (
        !Number.isFinite(start) ||
        !Number.isFinite(segment.end) ||
        segment.end <= start
      )
        return [];
      const measured = dub.generated_duration;
      const duration =
        measured !== null && Number.isFinite(measured) && measured > 0
          ? measured
          : segment.end - start;
      return [
        {
          id: dub.id,
          start,
          duration,
          audioPath: dub.audio_path,
          version: dub.generated_at ?? "",
        },
      ];
    })
    .sort((left, right) => left.start - right.start);
}

export function mixClipSourceTime(
  clip: MixDubClip,
  currentTime: number,
): number | null {
  return currentTime >= clip.start && currentTime < clip.start + clip.duration
    ? currentTime - clip.start
    : null;
}

const LOOKAHEAD_SECONDS = 2;
const TAIL_SECONDS = 0.5;

export function nearbyMixClips(
  clips: MixDubClip[],
  currentTime: number,
  lookahead = LOOKAHEAD_SECONDS,
  tail = TAIL_SECONDS,
): MixDubClip[] {
  if (!Number.isFinite(currentTime)) return [];
  return clips.filter(
    (clip) =>
      clip.start <= currentTime + lookahead &&
      clip.start + clip.duration >= currentTime - tail,
  );
}
