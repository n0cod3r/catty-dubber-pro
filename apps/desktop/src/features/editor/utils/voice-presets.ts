export type TtsTuning = { speed: number; pitch: number; volume: number };

export const DEFAULT_TTS_TUNING: TtsTuning = {
  speed: 1.25,
  pitch: 0,
  volume: 0,
};

export const EDGE_VOICE_PRESETS = [
  { id: "normal", label: "Normal", pitch: 0, gender: null },
  { id: "girl", label: "Girl", pitch: 20, gender: "female" },
  { id: "small-girl", label: "Small Girl", pitch: 30, gender: "female" },
  { id: "old-woman", label: "Old Woman", pitch: -20, gender: "female" },
  { id: "man", label: "Man", pitch: 20, gender: "male" },
  { id: "small-woman", label: "Small Woman", pitch: 30, gender: "female" },
  { id: "old-man", label: "Old Man", pitch: -20, gender: "male" },
] as const;

export function matchingVoicePreset(
  tuning: TtsTuning,
  gender?: string,
  preferredId?: string,
) {
  if (
    tuning.speed !== DEFAULT_TTS_TUNING.speed ||
    tuning.volume !== DEFAULT_TTS_TUNING.volume
  )
    return "custom";
  const candidates = EDGE_VOICE_PRESETS.filter(
    (preset) =>
      preset.pitch === tuning.pitch &&
      (!preset.gender || preset.gender === gender?.toLowerCase()),
  );
  // Preserve explicit choices when multiple named presets have identical tuning.
  const preferred = candidates.find((preset) => preset.id === preferredId);
  return (
    preferred?.id ?? (candidates.length === 1 ? candidates[0]!.id : "custom")
  );
}
