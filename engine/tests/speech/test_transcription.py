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
from catty_engine.speech.transcription import split_long_speech_regions


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


def test_transcribe_selection_uses_selected_backend_and_source_range(tmp_path: Path) -> None:
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


def test_long_speech_regions_are_split_into_dubbing_sized_chunks() -> None:
    regions = [SpeechRegion(start=2.0, end=16.5, confidence=0.9)]

    split = split_long_speech_regions(regions, max_duration=6.0)

    assert [(item.start, item.end) for item in split] == [
        (2.0, 8.0),
        (8.0, 14.0),
        (14.0, 16.5),
    ]
    assert all(item.confidence == 0.9 for item in split)


def test_short_vad_regions_keep_their_natural_boundaries() -> None:
    regions = [
        SpeechRegion(start=1.0, end=3.4),
        SpeechRegion(start=4.1, end=8.2),
    ]

    assert split_long_speech_regions(regions) == regions


def test_registry_allows_multiple_models() -> None:
    registry = AsrBackendRegistry()
    registry.register(FakeAsr())

    class FutureAsr(FakeAsr):
        id = "future-model"
        model = "future-v1"

    registry.register(FutureAsr())
    assert registry.ids() == ["future-model", "paraformer"]
