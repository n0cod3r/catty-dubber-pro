from pathlib import Path

from catty_engine.media.video_proxy import VideoProxyService


class FakeRunner:
    def __init__(self) -> None:
        self.calls = 0

    def create_playback_proxy(self, source: Path, destination: Path) -> None:
        del source
        self.calls += 1
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(b"proxy")


def test_valid_persisted_proxy_is_reused(tmp_path: Path) -> None:
    runner = FakeRunner()
    service = VideoProxyService(runner=runner)  # type: ignore[arg-type]
    source = tmp_path / "clip.mp4"
    source.write_bytes(b"video")

    first = service.prepare_playback_proxy(
        project_directory=tmp_path / "project", source=source
    )
    second = service.prepare_playback_proxy(
        project_directory=tmp_path / "project", source=source, existing_path=first
    )

    assert first == second
    assert runner.calls == 1


def test_missing_persisted_proxy_is_regenerated(tmp_path: Path) -> None:
    runner = FakeRunner()
    service = VideoProxyService(runner=runner)  # type: ignore[arg-type]
    source = tmp_path / "clip.mp4"
    source.write_bytes(b"video")

    first = service.prepare_playback_proxy(
        project_directory=tmp_path / "project", source=source
    )
    Path(first).unlink()
    second = service.prepare_playback_proxy(
        project_directory=tmp_path / "project", source=source, existing_path=first
    )

    assert second == first
    assert Path(second).is_file()
    assert runner.calls == 2
