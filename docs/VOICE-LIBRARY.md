# Voice library and VoxCPM2

Settings → Voices & TTS and Voice Clone share the application voice library. Both
engines expose Built-in and My voices. New profiles are saved immediately by Python;
the Settings footer is not needed for voice creation.

- Edge: choose Piseth or Sreymom, name the preset, adjust speed/pitch/volume, preview,
  and save. Defaults are 1.25× speed, 0 Hz pitch, and unchanged volume.
- VoxCPM2: import a recorded 3–30 second audio clip, customize an existing voice,
  or describe a voice. An optional transcript must match the imported recording.
  Preview and save a named profile. This flow does not train a model. Recording
  directly inside Catty is not implemented; import a recorded file.
- Built-ins include Man, Woman, Girl, Small Girl, Old Man, and Old Woman. Edge
  uses base voices plus pitch. VoxCPM2 uses fixed style descriptions to generate
  a reference once, and reuses that cached reference for subsequent cloning.
  These are generated local samples, not prerecorded files bundled in the binary.

VoxCPM2 is downloaded explicitly from Settings → Models, using the same background
install/resume/cancel/remove flow as translation models. It is kind `tts` and cannot
be selected as a translator. Synthesis uses only installed local weights, with no
implicit downloads, denoiser downloads, or external text-normalizer models. The
runtime is pinned to voxcpm 2.x through the engine dependency lock. Development
setups must run `uv sync --project engine --locked` after updating dependencies.
The first inference lazily loads the model on the configured auto/CPU/MPS/CUDA device.

## Persistence and editor integration

Application-managed data lives under `<Catty app data>/voices/`:

- `user/<uuid>/profile.json` and a normalized `reference.wav` for cloned voices.
- `builtin/<id>/reference.wav` for generated VoxCPM2 starting voices.
- `previews/` for Khmer samples, including cached built-in Edge samples.
- `trash/<uuid>/` for removed custom profiles. Built-ins cannot be removed.

`tts.library_*` methods list, create, preview, remove and copy profiles into projects.
There is no frontend database. The existing `tts.voices` list includes `library:<id>`
options; `tts.ensure_voice` resolves these into actual project VoiceProfile UUIDs.
Selecting a library voice therefore works with existing speaker/segment assignment
commands and their override precedence, without adding a workflow step. Changes to
the library refresh editor voice options through `catty:voices-changed`.

Using a cloned voice copies its reference into `assets/voices/<id>/reference.wav`
inside the project and stores a relative path. Project profiles retain their name,
engine, reference transcript, style and Edge tuning even if the application-library
entry is later removed. The library is immutable per profile ID; customize creates
another ID. Existing projects keep their own copies.

The TTS service routes project profiles to Edge or VoxCPM2 while keeping existing
progress, per-segment persistence and cancellation between segments. VoxCPM2 emits
WAV at its actual model sample rate and measures generated duration for timeline
waveforms. Edge controls are disabled for VoxCPM2; its persisted numeric tuning is
neutral (1×, 0 Hz, 0 volume adjustment). Duration fitting and in-generation interrupt
handling are not added here. VoxCPM2 inference is serialized and the model is reused.
Model/library logging goes to stderr so it cannot corrupt stdout RPC frames.

## Validation

Tests cover persistence, independent project references, input validation, built-in
sample reuse, local-only model loading, quiet RPC stdout, provider routing, and WAV
measurement. UI creation was exercised with a simulated backend. Runtime imports
were verified on the development Mac; actual VoxCPM2 voice quality and performance
still need testing after a user downloads its weights.
