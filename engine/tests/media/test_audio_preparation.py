from pathlib import Path
from uuid import uuid4

from catty_engine.media import (
    AudioAssetKind,
    AudioPreparationService,
)


class FakeAudioExtractor:
    def __init__(self) -> None:
        self.calls = 0

    def extract_speech_audio(
        self,
        source: Path,
        destination: Path,
        *,
        sample_rate: int = 16_000,
        channels: int = 1,
    ) -> None:
        self.calls += 1

        destination.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        destination.write_bytes(b"fake-wav")


def test_prepare_speech_audio(
    tmp_path: Path,
) -> None:
    source = tmp_path / "EP01.mp4"
    source.write_bytes(b"video")

    runner = FakeAudioExtractor()

    service = AudioPreparationService(runner=runner)

    episode_id = uuid4()

    asset = service.prepare_speech_audio(
        project_directory=tmp_path / "project",
        episode_id=episode_id,
        source=source,
    )

    assert runner.calls == 1

    assert asset.kind == AudioAssetKind.SPEECH
    assert asset.sample_rate == 16_000
    assert asset.channels == 1

    output = Path(asset.path)

    assert output.exists()
    assert output.name == "speech-16k-mono.wav"
    assert output.parent.parent.name == asset.source_fingerprint
    assert output.parent.parent.parent.name == "media"


def test_reuses_valid_cached_audio(
    tmp_path: Path,
) -> None:
    source = tmp_path / "EP01.mp4"
    source.write_bytes(b"video")

    runner = FakeAudioExtractor()

    service = AudioPreparationService(runner=runner)

    episode_id = uuid4()
    project_directory = tmp_path / "project"

    first = service.prepare_speech_audio(
        project_directory=project_directory,
        episode_id=episode_id,
        source=source,
    )

    second = service.prepare_speech_audio(
        project_directory=project_directory,
        episode_id=episode_id,
        source=source,
        existing_asset=first,
    )

    assert runner.calls == 1
    assert second == first


def test_reuses_prepared_audio_after_restart_with_new_episode_id(
    tmp_path: Path,
) -> None:
    source = tmp_path / "EP01.mp4"
    source.write_bytes(b"video")
    project_directory = tmp_path / "project"
    runner = FakeAudioExtractor()
    service = AudioPreparationService(runner=runner)

    first = service.prepare_speech_audio(
        project_directory=project_directory,
        episode_id=uuid4(),
        source=source,
    )

    # Simulate reopening Catty: frontend state has no previous AudioAsset and
    # currently creates a fresh episode UUID for the imported source.
    second = service.prepare_speech_audio(
        project_directory=project_directory,
        episode_id=uuid4(),
        source=source,
        existing_asset=None,
    )

    assert runner.calls == 1
    assert second == first
    assert Path(second.path).exists()


def test_reuses_legacy_prepared_audio_without_metadata(
    tmp_path: Path,
) -> None:
    source = tmp_path / "EP01.mp4"
    source.write_bytes(b"video")
    project_directory = tmp_path / "project"
    runner = FakeAudioExtractor()
    service = AudioPreparationService(runner=runner)

    first = service.prepare_speech_audio(
        project_directory=project_directory,
        episode_id=uuid4(),
        source=source,
    )

    metadata = Path(first.path).with_name("speech-16k-mono.json")
    metadata.unlink()

    second = service.prepare_speech_audio(
        project_directory=project_directory,
        episode_id=uuid4(),
        source=source,
        existing_asset=None,
    )

    assert runner.calls == 1
    assert second.path == first.path
    assert second.source_fingerprint == first.source_fingerprint
    assert metadata.exists()


def test_source_change_invalidates_cache(
    tmp_path: Path,
) -> None:
    source = tmp_path / "EP01.mp4"
    source.write_bytes(b"version-one")

    runner = FakeAudioExtractor()

    service = AudioPreparationService(runner=runner)

    episode_id = uuid4()
    project_directory = tmp_path / "project"

    first = service.prepare_speech_audio(
        project_directory=project_directory,
        episode_id=episode_id,
        source=source,
    )

    source.write_bytes(b"version-two-with-different-size")

    second = service.prepare_speech_audio(
        project_directory=project_directory,
        episode_id=episode_id,
        source=source,
        existing_asset=first,
    )

    assert runner.calls == 2

    assert second.source_fingerprint != first.source_fingerprint
    assert second.path != first.path


def test_missing_cached_file_regenerates_audio(
    tmp_path: Path,
) -> None:
    source = tmp_path / "EP01.mp4"
    source.write_bytes(b"video")

    runner = FakeAudioExtractor()

    service = AudioPreparationService(runner=runner)

    episode_id = uuid4()
    project_directory = tmp_path / "project"

    first = service.prepare_speech_audio(
        project_directory=project_directory,
        episode_id=episode_id,
        source=source,
    )

    Path(first.path).unlink()

    second = service.prepare_speech_audio(
        project_directory=project_directory,
        episode_id=episode_id,
        source=source,
        existing_asset=first,
    )

    assert runner.calls == 2
    assert Path(second.path).exists()
