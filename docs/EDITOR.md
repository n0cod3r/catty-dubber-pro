# Editor workspace

Catty's editor follows Freecut's separation of workspace chrome, preview, inspector,
and timeline while keeping the implementation focused on dubbing.

- `App.tsx` composes the shell, sidebar, source controller, and error boundary.
- `use-episode.ts` owns native/browser import, errors, object URL cleanup, and
  metadata updates guarded by episode ID.
- `EditorWorkspace` owns one source session. Its episode key resets playback,
  cuts, markers, selections, and mute state together when a source is replaced.
- `EditorPanels` owns the persistent timeline height and keyboard/pointer resize.
- The timeline separates toolbar, memoized track rows, document history, geometry,
  viewport/zoom, and pointer gestures. Track headers and clips share one scroll
  container so their vertical positions stay aligned.

## Available interactions

Import video through the Tauri picker, or a browser file picker in `pnpm dev:web`.
Scrub the ruler or tracks, use Space for playback, arrows to seek 1/30 second,
Shift + arrows to seek five seconds, and Home/End for the source boundaries.
Keyboard playback ignores inputs, buttons, and editable regions.

Focus the timeline for S (split the selected clip or linked source video/audio), N (snapping), M
(marker), and Ctrl/Cmd + Z / Shift + Z (undo/redo document edits). Locks protect linked
splits and undo/redo. Markers seek on click and are removed by double-click.
Snapping uses an eight-pixel threshold; Shift temporarily bypasses it.

Ctrl/Cmd + wheel zooms around the pointer. Toolbar zoom anchors to the playhead;
Fit restores the whole episode. Dragging near a viewport edge scrolls the timeline.
Scrub updates are coalesced per animation frame; pointer cancellation and unmount
cancel pending work. Ruler tick generation is limited to the visible time range.

The sidebar collapses with its header control or Ctrl/Cmd + B. Project, Episodes,
Voice library, and Editor settings switch sidebar content. Settings includes the
follow-playhead toggle. The inspector has keyboard-accessible Audio, Dialogue, Khmer,
and Media tabs.

## Current limits

Video and source audio play from the original media file. Splits create contiguous
linked segment boundaries; trimming, offline rendering, and exporting edits are
not implemented. Changes are session-only; only the timeline panel height persists.
Transcript, translation, and voice generation require the dubbing engine and show
explicit empty states until connected. Frame stepping uses 1/30 second because
source frame-rate detection is not available yet.

## Validation

`pnpm test:editor` runs timeline geometry, snapping, ruler bounds, and history tests
using Node's native TypeScript support (Node 22.18+ or Node 24).
Run `pnpm typecheck`, `pnpm lint`, and `pnpm build:web` for the workspace checks.

The browser flow was also checked with a generated WebM: import, seek, split,
undo/redo, markers, mute, locks, zoom/fit, sidebar collapse, keyboard playback,
resize, media inspection, source replacement, and invalid-file recovery.

## Multiple layers and media graphics

The editor session now owns a document of independent `layers` and `clips` in
`features/timeline/stores/timeline-reducer.ts`. Video, audio, subtitle, and graphic clips share
explicit timeline start/duration and source offsets. The default source video,
source audio, and dub layers can be extended using **Layer** in the toolbar.
Layer menus reorder layers or remove empty ones; header buttons lock, hide, or
mute them. The source layers are protected from removal. These document edits,
including linked splits, use a bounded undo/redo history.

Add a subtitle or graphic layer, then click its empty lane to insert a five-second
caption or title at the playhead. Select it to edit **Layer text** and press Enter
to apply. These text overlays render immediately in the preview, within the
source video's fitted frame. Visible layers above the source video composite in
layer order. The graphic renderer currently supports text titles; image assets,
transforms, clip trimming, and independent media sources are future work.

`features/timeline/workers/media-visuals.worker.ts` decodes source media with
Mediabunny in a module worker. Video thumbnails are genuine sampled video frames,
requested for the visible viewport as it changes. The session caches at most 256
160×90 bitmaps and releases their GPU resources when replaced or evicted.
Audio is decoded progressively into signed min/max peaks using presentation
timestamps, merging the first two channels without phase cancellation. Raw PCM
is released sample by sample; peak storage is capped at one million bins.

Filmstrips and waveforms draw on DPR-aware canvases restricted to the visible
clip window, with a small overscan. Splitting preserves source offsets, so both
visuals remain aligned to the source. The preview continues playing independently
while decoding runs. Source replacement terminates the worker and clears all
cached bitmaps and peaks. Loading, missing-audio, and unsupported-codec states are
shown in the clip rather than replaced with synthetic graphics. Codec availability
depends on the WebView/browser; see the [Mediabunny codec documentation](https://mediabunny.dev/guide/supported-formats-and-codecs).

Additional tests cover dynamic layers, linked source offsets, protected layers,
metadata initialization, timestamped stereo peaks, and bounded canvas windows.
Browser checks verify painted canvas pixels, live Khmer captions and title
layers, visibility, reordering, zoom/scroll redraws, and source replacement, using
both Vite development mode and the production build's module worker.

## Preview and inspector sizing

Drag the vertical divider between Preview and Inspector to resize the panels.
The inspector width persists across reloads and source changes and is clamped to
the current window size. Arrow Left/Right resize a focused divider, Home/End use
its limits, and double-click restores the default width. The timeline divider
continues to support vertical resizing independently.

The preview resolves the front visible video clip at the playhead and reads its
source dimensions. Video and text overlays occupy one fitted frame, with no
assumed 16:9 ratio while metadata loads. Both portrait and landscape footage
retain their source aspect ratio as either divider or the window changes size.
The last video frame remains visible at the end of playback.

## Move and remove clips

Drag the body of a clip to change its timeline start, or drop it on an unlocked
layer of the same type. Linked source video and audio segments move together;
the audio keeps its audio layer when video is transferred between video layers.
Splits retain the link only to the corresponding segment for move/delete edits.
Snapping aligns clip edges to other clips, markers, and the playhead; hold Shift
to bypass it. When a drag overlaps another clip, placement stops at the nearest
valid contact boundary, even with snapping off. Small positive gaps remain exactly
as placed; collision contact does not magnetically pull nearby clips together.
Locked, incompatible, and outside-lane drops are rejected.
Escape, pointer cancellation, and lost capture discard the drag. A completed move
creates one undo entry.

Select a clip and press Delete/Backspace, use the toolbar trash button, or
right-click **Remove clip**. This also works for original and added source clips.
A corresponding linked video/audio segment is removed together unless either
layer is locked. The source asset remains in the project for re-adding, and
undo/redo restores the timeline edit. Deleting the last clips leaves an empty
timeline rather than re-inserting the original source.

Playback now uses the timeline clock, including gaps and clips moved past the
original media duration. Video and each active audio clip seek to their source
offsets independently. Removing an audio clip stops its media element immediately.
