import assert from "node:assert/strict";
import test from "node:test";

import {
  dubMixClips,
  mixClipSourceTime,
  nearbyMixClips,
} from "../apps/desktop/src/features/preview/utils/dub-mix.ts";

const episode = {
  id: "episode",
  dialogueSegments: [
    {
      id: "a",
      start: 2,
      end: 4,
      sourceLanguage: "zh",
      sourceText: "一",
      confidence: null,
      translation: null,
    },
    {
      id: "b",
      start: 6,
      end: 8,
      sourceLanguage: "zh",
      sourceText: "二",
      confidence: null,
      translation: null,
    },
    {
      id: "c",
      start: -1,
      end: 0.5,
      sourceLanguage: "zh",
      sourceText: "三",
      confidence: null,
      translation: null,
    },
    {
      id: "broken",
      start: 10,
      end: 10,
      sourceLanguage: "zh",
      sourceText: "四",
      confidence: null,
      translation: null,
    },
  ],
  dubSegments: [
    {
      id: "dub-b",
      dialogue_segment_id: "b",
      status: "ready",
      audio_path: "/audio/b.wav",
      generated_duration: 1.5,
      generated_at: "v2",
    },
    {
      id: "dub-a",
      dialogue_segment_id: "a",
      status: "ready",
      audio_path: "/audio/a.wav",
      generated_duration: null,
      generated_at: "v1",
    },
    {
      id: "dub-outdated",
      dialogue_segment_id: "c",
      status: "outdated",
      audio_path: "/audio/c.wav",
      generated_duration: 1,
      generated_at: "v1",
    },
    {
      id: "dub-no-file",
      dialogue_segment_id: "a",
      status: "ready",
      audio_path: null,
      generated_duration: 1,
      generated_at: "v1",
    },
    {
      id: "dub-broken",
      dialogue_segment_id: "broken",
      status: "ready",
      audio_path: "/audio/broken.wav",
      generated_duration: 1,
      generated_at: "v1",
    },
    {
      id: "dub-orphan",
      dialogue_segment_id: "missing",
      status: "ready",
      audio_path: "/audio/orphan.wav",
      generated_duration: 1,
      generated_at: "v1",
    },
  ],
};

test("mix clips only include ready dubs with audio and valid segment timing", () => {
  const clips = dubMixClips(episode);
  assert.deepEqual(
    clips.map((clip) => clip.id),
    ["dub-a", "dub-b"],
  );
  assert.deepEqual(clips[0], {
    id: "dub-a",
    start: 2,
    duration: 2,
    audioPath: "/audio/a.wav",
    version: "v1",
  });
});

test("mix clips prefer measured audio duration over the segment window", () => {
  const clip = dubMixClips(episode).find((item) => item.id === "dub-b");
  assert.equal(clip.duration, 1.5);
});

test("mix clips clamp negative starts and reject zero-length segments", () => {
  const mixed = dubMixClips({
    ...episode,
    dubSegments: episode.dubSegments
      .filter((dub) => ["dub-outdated", "dub-broken"].includes(dub.id))
      .map((dub) => ({ ...dub, status: "ready", audio_path: "/audio/x.wav" })),
  });
  assert.deepEqual(
    mixed.map((clip) => clip.id),
    ["dub-outdated"],
  );
  assert.equal(mixed[0].start, 0);
  assert.equal(mixed[0].duration, 1);
});

test("mix clip source time is only defined inside the clip window", () => {
  const [clip] = dubMixClips(episode);
  assert.equal(mixClipSourceTime(clip, 1.99), null);
  assert.equal(mixClipSourceTime(clip, 2), 0);
  assert.equal(mixClipSourceTime(clip, 3.25), 1.25);
  assert.equal(mixClipSourceTime(clip, 4), null);
});

test("nearby mix clips preload ahead and keep a short tail", () => {
  const clips = dubMixClips(episode);
  assert.deepEqual(
    nearbyMixClips(clips, 3).map((clip) => clip.id),
    ["dub-a"],
  );
  assert.deepEqual(
    nearbyMixClips(clips, 4.2).map((clip) => clip.id),
    ["dub-a", "dub-b"],
  );
  assert.deepEqual(
    nearbyMixClips(clips, 7.8).map((clip) => clip.id),
    ["dub-b"],
  );
  assert.deepEqual(nearbyMixClips(clips, Number.NaN), []);
});
