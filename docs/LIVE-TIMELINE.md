# Live timeline progress

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

## Translation

The read-only Khmer translation row derives saved text from the Episode. Existing
translation progress identifies the active batch and supplies completed/total counts.
Each saved batch updates the corresponding clips in place. Pending and failed clips
remain distinguishable from translated dialogue. This is batch progress, not token
streaming. Saved translations remain visible after completion, failure, or reopen.

## TTS

The Khmer dub row derives ready assets from persisted `dub_segments`, matched to dialogue
IDs. The generation hook tracks the requested targets and removes each from its pending
list on `saved`. Clips show Queued, Generating, Ready, Failed, or Outdated. Ready clips use
the measured generated duration at the dialogue start; this does not implement duration
fitting. Cancel/failure clears pending presentation and retains successful saved audio.
An empty default dub row is reused; existing manual clips receive a separate result row.

Visible ready clips decode their own audio using the existing media worker. Decoding is
limited to two workers, with cancellation on unsubscribe and a 64-entry cache containing
128 peak values per clip. Paths plus generation timestamps distinguish regenerated files.
The source-video waveform is never reused for generated speech. Decode errors are shown
without blocking audio preview. A clip's Play button auditions that completed file; only
one audition plays per row, and it stops on episode/project changes or asset replacement.
This does not add automatic dub mixing to timeline playback or export.

These rows never write to TimelineDocument, Undo/Redo, or project.json. Python persistence
remains authoritative. TTS subscribes before submitting the command, and scopes events and
async completions to the operation, project, episode, and session generation. Switching
away and back invalidates old requests. Final RPC results and project reload on error
recover saved segments even if progress delivery races or fails.
