# Live transcription timeline

The editor forwards its existing, session-guarded transcription progress to the timeline.
`TranscriptionPreviewTrack` renders a separate read-only draft row; it never writes to
`TimelineDocument`, history, playback, or project persistence. The previous saved dialogue
remains visible while a replacement is processing.

Drafts appear for matching project/episode progress only while transcription is active.
They are sorted by source time because FunASR chunks may finish out of order. IDs include
the operation and segment IDs. Repeated snapshots replace the rendered draft list.
Invalid ranges are discarded and display ranges are clipped to the media duration.

Completion, failure, an episode/project change, or the end of the operation removes the
preview. The existing saved Episode flow remains responsible for updating the normal
Dialogue subtitles track. Clicking a draft seeks to its start; drafts cannot be edited,
dragged, split, deleted, or added to Undo/Redo. Progress does not seek or reset zoom/scroll.
Updates are per ASR chunk, not token streaming. Final alignment can change text and timing.

## TTS follow-up

TTS live clips are not implemented here. Connect them once the Edge foundation exposes
its actual progress and persisted audio contracts. At minimum, the UI needs operation,
project, episode and segment identity, per-segment status, and notification that an audio
file is ready, including its usable path and measured duration. Failed/retried segments
must update the same item; stale operations must be ignored. Waveforms should be decoded
from completed audio files. Do not use the source-video waveform for generated speech.
