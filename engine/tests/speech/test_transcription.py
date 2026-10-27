from pathlib import Path
from uuid import uuid4

import pytest

from catty_engine.media.audio import AudioAsset, AudioAssetKind
from catty_engine.speech import (
    AsrBackendRegistry,
    SpeechRegion,
    TranscriptSegment,
    TranscriptionService,
    WholeClipVad,
)


class PreparedAudio:
    def prepare_speech_audio(self, **kwargs: object) -> AudioAsset:
        project = Path(str(kwargs["project_directory"]))
        path = project / "speech.wav"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"wav")
        return AudioAsset(
            path=str(path),
            kind=AudioAssetKind.SPEECH,
            sample_rate=16_000,
            channels=1,
            source_fingerprint="source",
        )


class FakeAsr:
    id = "paraformer"
    model = "test-paraformer"

    def transcribe(
        self, audio: Path, regions: list[SpeechRegion], *, language: str
    ) -> list[TranscriptSegment]:
        assert audio.name == "speech.wav"
        assert language == "zh"
        return [
            TranscriptSegment(start=region.start, end=region.end, text="你好")
            for region in regions
        ]


def test_transcribe_selection_uses_selected_backend_and_source_range(
    tmp_path: Path,
) -> None:
    registry = AsrBackendRegistry()
    registry.register(FakeAsr())
    service = TranscriptionService(
        asr_backends=registry,
        vad=WholeClipVad(),
        audio_preparation=PreparedAudio(),  # type: ignore[arg-type]
    )

    result = service.transcribe(
        project_directory=tmp_path,
        episode_id=uuid4(),
        source=tmp_path / "episode.mp4",
        backend_id="paraformer",
        language="zh",
        source_start=12.5,
        duration=3.0,
    )

    assert result.backend == "paraformer"
    assert result.model == "test-paraformer"
    assert result.segments[0].start == 12.5
    assert result.segments[0].end == 15.5
    assert result.segments[0].text == "你好"
    assert result.speaker_error is None


def test_vad_regions_are_passed_to_asr_without_fixed_six_second_chopping(
    tmp_path: Path,
) -> None:
    class NaturalVad:
        id = "test-vad"

        def detect(self, audio, *, start=0, duration=None):
            return [
                SpeechRegion(start=start + 1.2, end=start + 2.8),
                SpeechRegion(start=start + 4.0, end=start + 5.1),
            ]

    registry = AsrBackendRegistry()
    registry.register(FakeAsr())
    service = TranscriptionService(
        asr_backends=registry,
        vad=NaturalVad(),  # type: ignore[arg-type]
        audio_preparation=PreparedAudio(),  # type: ignore[arg-type]
    )

    result = service.transcribe(
        project_directory=tmp_path,
        episode_id=uuid4(),
        source=tmp_path / "episode.mp4",
        backend_id="paraformer",
        language="zh",
        source_start=0.0,
        duration=7.0,
    )

    assert [(segment.start, segment.end) for segment in result.segments] == [
        (1.2, 2.8),
        (4.0, 5.1),
    ]


def test_registry_get_has_no_lazy_model_or_network_side_effects() -> None:
    registry = AsrBackendRegistry()
    with pytest.raises(ValueError, match="Unknown ASR backend"):
        registry.get("paraformer")
    assert registry.ids() == []


def test_paraformer_resolves_to_funasr_and_never_sherpa_small() -> None:
    from catty_engine.speakers.funasr import FunASRParaformerBackend
    from catty_engine.speech.model_manager import ModelManager
    from catty_engine.speech.runtime import create_asr_registry

    registry = create_asr_registry("paraformer", {})
    assert isinstance(registry.get("paraformer"), FunASRParaformerBackend)
    with pytest.raises(ValueError, match="FunASR"):
        ModelManager().ensure_asr("paraformer")


def test_factory_uses_integrated_vad_and_speakers_for_paraformer(
    monkeypatch,
) -> None:
    from catty_engine.speech import runtime

    def unexpected(*args, **kwargs):
        raise AssertionError("integrated backends must not build external VAD")

    monkeypatch.setattr(runtime, "create_vad", unexpected)
    service = runtime.create_transcription_service(
        backend_id="paraformer",
        asr_config={},
        vad_backend="silero",
        vad_config={},
    )
    assert service is not None


def test_registry_allows_multiple_models() -> None:
    registry = AsrBackendRegistry()
    registry.register(FakeAsr())

    class FutureAsr(FakeAsr):
        id = "future-model"
        model = "future-v1"

    registry.register(FutureAsr())
    assert registry.ids() == ["future-model", "paraformer"]
