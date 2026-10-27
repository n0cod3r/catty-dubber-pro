# Smart Speaker Detection

Transcribe remains one action. The Paraformer button now uses the reviewed local
FunASR 1.4.16 pipeline: prepared 16 kHz mono audio → FSMN VAD → Paraformer-large →
CT punctuation/sentence timing → CAM++ embeddings/native clustering → persistence.
The native clustering merge threshold is 0.78, matching the approved benchmark.
No fixed speaker count is supplied. CPU inference with two Torch threads is the
portable baseline; macOS Apple Silicon was tested, Windows runtime is not yet tested.

SenseSmall retains its existing Sherpa ASR and Silero segmentation. It obtains
speaker turns from the same FunASR pipeline and assigns each dialogue segment to
the cluster with the greatest total timestamp overlap. This runs both recognition
pipelines and costs more than Paraformer. Gaps remain unassigned. Selection timestamps
are converted from range-relative milliseconds to source-relative seconds.

Python ProjectService creates EpisodeSpeaker records and DialogueSegment.speaker_id
in one project.json save. Re-transcription replaces old dialogue/speakers and clears
obsolete dub references. It resets the existing editor dialogue undo history.
Speaker IDs are episode/run-local, with badges S1, S2, etc.; they are not stable
character identities across episodes. Saved projects restore badges without inference.
Zustand remains editor/session state and does not become a database.

Select a dialogue row to correct its speaker using the compact Speaker dropdown.
Choose an existing speaker, Unassigned, or New speaker. The command validates episode
ownership and expected speaker identity, updates both ownership directions, removes
obsolete generated audio for the edited segment, and persists. The existing guarded
snapshot history supports correction Undo/Redo, including newly created speakers.
Split inherits speaker; a merge across different speakers becomes unassigned.

## Installation and models

Run `uv sync --directory engine` after updating dependencies and restart Catty to
restart its persistent Python process. The engine still uses Python 3.13. First
transcription downloads approximately 2.1 GB of model weights/configuration from
public funasr Hugging Face repositories; subsequent runs use the local cache,
including offline operation after the full download completes. No audio is uploaded.
Pinned model revisions are in `engine/src/catty_engine/speakers/funasr.py`.
Models load lazily; health, import and project open do not import Torch/FunASR.
One pipeline instance is cached in the persistent process. Diagnostics use stderr,
keeping stdout reserved for JSON IPC.

Model cache uses the existing CATTY_MODEL_DIR OS-specific root, under `funasr`.
For an existing local model bundle, CATTY_FUNASR_MODEL_DIR may point to a directory
containing paraformer-zh, fsmn-vad, ct-punc and campplus subdirectories. Such an
explicit override is trusted operator configuration; use the pinned weights.
Interrupted/incomplete model caches are checked and downloads retried on next use.
A failed inference does not replace persisted dialogue. A successful empty/silent
transcription replaces dialogue with an empty result.

CAM++ clusters are acoustic groups, not gender labels. They can combine different
actors, especially brief or similar voices; the reviewed episode produced two
clusters across multiple characters, which the operator accepted for this workflow.
Automatic gender classification, Piseth/Sreymom voice mapping, translation and TTS
are separate future work. The UI does not infer gender from S1/S2 or introduce an
Assign Speakers workflow step. Reliable overlapping speech and per-character identity
still require human review and broader benchmark annotation.
