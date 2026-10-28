import assert from "node:assert/strict";
import test from "node:test";

import {
  DEFAULT_TTS_TUNING,
  matchingVoicePreset,
} from "../apps/desktop/src/features/editor/utils/voice-presets.ts";

test("voice presets distinguish genders sharing the same pitch", () => {
  const tuning = { ...DEFAULT_TTS_TUNING, pitch: 20 };
  assert.equal(matchingVoicePreset(tuning, "Female", "man"), "girl");
  assert.equal(matchingVoicePreset(tuning, "Male", "girl"), "man");
  assert.equal(
    matchingVoicePreset({ ...tuning, pitch: -20 }, "Male"),
    "old-man",
  );
  assert.equal(
    matchingVoicePreset({ ...tuning, pitch: -20 }, "Female"),
    "old-woman",
  );
});

test("identical female presets preserve explicit selection and do not guess an ambiguous name", () => {
  const tuning = { ...DEFAULT_TTS_TUNING, pitch: 30 };
  assert.equal(
    matchingVoicePreset(tuning, "Female", "small-woman"),
    "small-woman",
  );
  assert.equal(
    matchingVoicePreset(tuning, "Female", "small-girl"),
    "small-girl",
  );
  assert.equal(matchingVoicePreset(tuning, "Female"), "custom");
  assert.equal(matchingVoicePreset(tuning, "Male", "small-girl"), "custom");
});

test("manual speed or volume changes are Custom and Normal works with either voice", () => {
  assert.equal(matchingVoicePreset(DEFAULT_TTS_TUNING, "Male"), "normal");
  assert.equal(matchingVoicePreset(DEFAULT_TTS_TUNING, "Female"), "normal");
  assert.equal(
    matchingVoicePreset({ ...DEFAULT_TTS_TUNING, speed: 1 }, "Female"),
    "custom",
  );
  assert.equal(
    matchingVoicePreset({ ...DEFAULT_TTS_TUNING, volume: 10 }, "Male"),
    "custom",
  );
});
