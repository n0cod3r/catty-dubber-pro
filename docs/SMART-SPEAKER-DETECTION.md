# Smart Speaker Detection

Transcribe remains one action. The default Paraformer path is Catty's Smart Chinese pipeline:

`16 kHz mono analysis audio → FSMN-VAD → Paraformer-large → CT-Punc sentence timing → CAM++ → speaker-aware dialogue → project.json`

Paraformer-large + CT-Punc is the canonical Chinese transcript. There is one production Paraformer backend and one cached FunASR model stack; the sherpa Paraformer-small archive is no longer downloaded or exported. `punc_segment` provides sentence-oriented boundaries. FSMN-VAD keeps up to 30 seconds of recognition context, so Catty does not pre-cut audio into fixed six-second bins.

After recognition, `split_long_dialogue` shortens dialogue that exceeds the six-second usability target. It splits at Chinese punctuation (strong before weak) and uses proportional character timing only when no punctuation boundary exists. Splits preserve source text, order, timing bounds and the recognized speaker. Six seconds is a post-ASR target, not a VAD or ASR boundary.

The native CAM++ clustering merge threshold is 0.78. Catty does not require a fixed speaker count. Speaker IDs are episode/run-local acoustic clusters (`S1`, `S2`, ...), not stable character identities or gender labels. Missing speaker metadata does not remove recognized dialogue.

## Runtime policy

Catty is Windows-first for production while remaining fully developable on macOS Apple Silicon.

- Windows + NVIDIA CUDA: automatically use CUDA when PyTorch reports it available.
- Windows without CUDA: use CPU.
- macOS Apple Silicon: automatic mode uses CPU for the full FunASR stack because this is the portable baseline. MPS can be explicitly tested with `CATTY_FUNASR_DEVICE=mps`.
- `CATTY_FUNASR_DEVICE=cpu|cuda|mps|auto` overrides device selection. An unavailable explicitly requested accelerator fails clearly instead of silently changing behavior.
- CPU inference uses half of logical cores, bounded to 2-8 threads. `CATTY_FUNASR_CPU_THREADS=1..32` overrides this.

SenseSmall keeps its Sherpa ASR + Silero VAD path and may use FunASR for speaker-turn matching. Paraformer uses one integrated FunASR ASR/VAD/punctuation/speaker pass. Both backends are built by `create_transcription_service`; the IPC layer has no Paraformer special case. Integrated backends own FSMN-VAD, so external Silero settings apply only to SenseSmall.

If CAM++ or speaker post-processing fails, Catty retries the **same loaded pipeline** with `return_spk_res=False`, keeping canonical ASR, VAD and CT-Punc. It returns editable unassigned dialogue with `speaker_error` instead of losing the transcript. FunASR exposes no speaker-only exception boundary, so this retry is also the classifier: if the non-speaker retry fails, the real transcription error is raised with the original failure chained.

When a separate speaker-turn matcher is used, a label is accepted only when the winning speaker covers at least 50% of the dialogue and at least 300 ms (bounded by the dialogue duration). Tiny overlaps remain unassigned rather than becoming a false confident speaker.

## Persistence and editing

Python `ProjectService` and `project.json` remain the source of truth. Successful transcription persists `EpisodeSpeaker` records, `DialogueSegment.speaker_id`, and speaker `segment_ids` together. A failed ASR transcription does not replace saved dialogue. A diarization-only failure is not an ASR failure: recognized dialogue survives, `processing.transcription` is `completed`, and `processing.speakers` is `failed` with `processing.speaker_error`. The editor shows a compact, dismissible-free warning and keeps manual speaker correction available. Reopening the project reads the persisted failure state.

The editor shows compact speaker badges. Selecting a dialogue allows correction to an existing speaker, Unassigned, or New speaker. Corrections persist through the Python domain and participate in the existing guarded dialogue Undo/Redo history. Split inherits the speaker; merging different speakers becomes unassigned.

There is no required Assign Speakers workflow step. User flow remains:

`Import → Transcribe → review/correct only if needed → Translate → Generate Dubbing → Export`

## Models and cache

Pinned revisions live in `engine/src/catty_engine/speakers/funasr.py` for:

- `funasr/paraformer-zh`
- `funasr/fsmn-vad`
- `funasr/ct-punc`
- `funasr/campplus`

Models use the existing OS-specific `CATTY_MODEL_DIR` root under `funasr`. `CATTY_FUNASR_MODEL_DIR` can point to a preinstalled bundle containing `paraformer-zh`, `fsmn-vad`, `ct-punc`, and `campplus` subdirectories. The override is validated before inference. Normal downloads first reuse a complete local Hugging Face cache and only access the network when required files are missing. Download failures produce a retryable error; incomplete model sets are never loaded.

Models load lazily so health, project open and media import do not import Torch/FunASR. The persistent Python process caches loaded pipelines. Diagnostics are redirected to stderr because stdout is reserved for JSON IPC.

## Known limits

CAM++ clusters speakers acoustically. Brief, similar, noisy or overlapping voices can be merged or misassigned. Manual correction is intentionally the fallback.

The 50% / 300 ms coverage floor applies to the separate speaker-turn matcher used by SenseSmall. FunASR's integrated `punc_segment` labels are assigned by its internal maximum-overlap `distribute_spk`, which does not expose a supported fine-grained turn list or a coverage score; Catty does not patch those internals. A dedicated diarizer port is the seam for changing that later.

Long-dialogue splitting uses punctuation boundaries and proportional character timing because word-level timestamps are not persisted. It is a usability pass, not word-accurate alignment. Retrying speaker detection currently means re-transcription; there is no annotate-only retry operation. Cross-episode character identity, gender classification, translation and TTS are separate work and are not inferred from `S1/S2` labels.
