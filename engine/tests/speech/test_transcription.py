from pathlib import Path
from uuid import uuid4

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


def test_registry_allows_multiple_models() -> None:
    registry = AsrBackendRegistry()
    registry.register(FakeAsr())

    class FutureAsr(FakeAsr):
        id = "future-model"
        model = "future-v1"

    registry.register(FutureAsr())
    assert registry.ids() == ["future-model", "paraformer"]
