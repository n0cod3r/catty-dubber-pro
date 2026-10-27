# Smart Speaker Detection

Transcribe remains one action. The default Paraformer path is Catty's Smart Chinese pipeline:

`16 kHz mono analysis audio → FSMN-VAD → Paraformer-large → CT-Punc sentence timing → CAM++ → speaker-aware dialogue → project.json`

Paraformer-large + CT-Punc is the canonical Chinese transcript. Catty no longer runs the sherpa Paraformer-small model in parallel and no longer throws away the large model's punctuated text. `punc_segment` provides sentence-oriented caption boundaries. FSMN-VAD keeps up to 30 seconds of recognition context; Catty does not pre-cut the audio into fixed six-second subtitle bins.

The native CAM++ clustering merge threshold is 0.78. Catty does not require a fixed speaker count. Speaker IDs are episode/run-local acoustic clusters (`S1`, `S2`, ...), not stable character identities or gender labels. Missing speaker metadata does not remove recognized dialogue.

## Runtime policy

Catty is Windows-first for production while remaining fully developable on macOS Apple Silicon.

- Windows + NVIDIA CUDA: automatically use CUDA when PyTorch reports it available.
- Windows without CUDA: use CPU.
- macOS Apple Silicon: automatic mode uses CPU for the full FunASR stack because this is the portable baseline. MPS can be explicitly tested with `CATTY_FUNASR_DEVICE=mps`.
- `CATTY_FUNASR_DEVICE=cpu|cuda|mps|auto` overrides device selection. An unavailable explicitly requested accelerator fails clearly instead of silently changing behavior.
- CPU inference uses half of logical cores, bounded to 2-8 threads. `CATTY_FUNASR_CPU_THREADS=1..32` overrides this.

SenseSmall keeps its Sherpa ASR + Silero VAD path and may use FunASR for speaker-turn matching. Paraformer uses one integrated FunASR ASR/VAD/punctuation/speaker pass. If CAM++ or speaker post-processing fails, Catty retries the same large Paraformer + FSMN-VAD + CT-Punc stack without the speaker model and returns editable unassigned dialogue with `speaker_error` instead of losing the transcript.

When a separate speaker-turn matcher is used, a label is accepted only when the winning speaker covers at least 50% of the dialogue and at least 300 ms (bounded by the dialogue duration). Tiny overlaps remain unassigned rather than becoming a false confident speaker.

## Persistence and editing

Python `ProjectService` and `project.json` remain the source of truth. Successful transcription persists `EpisodeSpeaker` records, `DialogueSegment.speaker_id`, and speaker `segment_ids` together. A failed ASR transcription does not replace saved dialogue. A diarization-only failure is not an ASR failure: recognized dialogue survives and can be corrected manually.

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

CAM++ clusters speakers acoustically. Brief, similar, noisy or overlapping voices can be merged or misassigned. Manual correction is intentionally the fallback. Cross-episode character identity, gender classification, translation and TTS are separate work and are not inferred from `S1/S2` labels.
