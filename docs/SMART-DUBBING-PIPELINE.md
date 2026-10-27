# Smart Dubbing Pipeline

## Product principle

Automation first, correction second. Catty builds the dubbing project; the user
makes decisions when Catty is uncertain or when the user wants to override a
result. Internal processing tasks must not become mandatory setup milestones.

The five major actions are:

```text
Import → Transcribe → Translate to Khmer → Generate Dubbing → Export
```

Speaker assignment and voice mapping are optional correction tools. A normal
project must not require assigning every dialogue speaker or configuring every
voice before continuing.

## Current implementation

Import and transcription include internal audio preparation, VAD, ASR and automatic
segmentation. Dialogue text editing, manual Split/Merge, persistent project data,
Undo/Redo and history isolation are implemented. Speaker detection, translation,
dubbing generation and export described below are planned capabilities, not
claims about the current runtime.

## Next milestone: Smart Speaker Detection

One **Transcribe** action should produce dialogue with speakers automatically:

```text
Audio preparation
  → VAD / ASR / segmentation
  → speaker detection and clustering
  → Speaker 1, Speaker 2, …
  → persisted dialogue and subtitle timeline
```

The engine owns speaker analysis and clustering. ProjectService saves speakers,
segment speaker IDs and corresponding speaker segment references together in
`project.json`. Frontend state derives from the returned persisted episode.

Inspector displays compact speaker badges, such as `[S1]` and `[S2]`, beside
rows. Clicking a badge allows a correction. Renaming a speaker is optional. The
normal transcription flow does not open an assignment wizard.

Acceptance criteria:

- One action returns dialogue and automatic speaker assignments without a
  separate assignment step.
- Recurring appearances of a detected voice share a speaker within the episode.
- Uncertain or overlapping speech is marked for optional review; uncertainty
  must not be presented as a confident classification. Analysis failure leaves
  usable dialogue and an actionable retry instead of discarding transcription.
- Manual corrections persist and synchronize across Inspector and Timeline.
- Reopening restores speakers and corrected assignments. Split/Merge and
  Undo/Redo preserve valid speaker references.
- Re-transcription explicitly replaces derived results; a background retry must
  not silently replace a user's corrections.

Speaker/character identities and gender labels must not be inferred solely from
speaker numbering. Uncertain voice attributes can use an available default
without forcing the user through manual assignment.

## Following milestone: Smart Khmer Translation

One **Translate to Khmer** action translates dialogue with neighboring lines and
speaker context, retaining segment identities and timing. The engine prepares
Khmer subtitles automatically and persists the result. Users review and correct
Khmer only when needed. Translation remains linked to its source segment so a
source correction invalidates the corresponding derived result.

## Smart dubbing generation

One **Generate Dubbing** action chooses available voice defaults, generates TTS,
fits duration, places generated audio and prepares the mix. Default voice mapping
is ready to run and consistent for each speaker. Optional per-speaker voice
overrides remain available; missing or uncertain attributes do not introduce a
mandatory assignment step. Generation reports failures and supports retrying
failed work while preserving completed results and user overrides.

## Architecture and scope

- `project.json`: persistent source of truth.
- Python services and ProjectService: processing and domain mutations.
- Frontend command/history orchestration: requests, progress and corrections.
- Zustand: editor/session representation.
- Inspector: interaction and review.

VAD, segmentation, speaker clustering, voice mapping, timing fit, cache and audio
preparation remain internal intelligence. Progress may describe these operations
without turning them into required user actions.

Dialogue revision tracking and word/character timestamp-aware or semantic
splitting remain later work. Reliable timestamp splitting belongs with a future
ASR pipeline/model upgrade and must not be forced into the current Paraformer
flow. They are not prerequisites for starting Smart Speaker Detection.
