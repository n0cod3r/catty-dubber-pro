import json
import subprocess
import sys
from pathlib import Path

from catty_engine.ipc import handle_request
from catty_engine.media.errors import FFprobeNotFoundError


def test_health_lists_available_operations() -> None:
    response = handle_request(
        {"version": 1, "id": "health-1", "method": "health", "params": {}}
    )
    assert response["id"] == "health-1"
    assert response["result"]["capabilities"] == [
        "media.probe",
        "audio.prepare",
        "project.create",
        "project.open",
        "project.prepare_episode",
        "project.rebuild_proxy",
        "project.import_episode",
        "project.dialogue_split",
        "project.dialogue_merge_next",
        "project.dialogue_restore",
        "project.dialogue_update_text",
        "project.dialogue_update_translation",
        "project.dialogue_assign_speaker",
        "speech.transcribe",
        "settings.get",
        "settings.update",
        "settings.credential_add",
        "settings.credential_remove",
        "translation.providers",
        "translation.models",
        "translation.test_connection",
        "translation.translate_episode",
        "models.list",
        "models.install",
        "models.install_status",
        "models.remove",
        "speakers.funasr-campplus",
        "asr.paraformer",
        "asr.sense-small",
        "vad.silero",
        "system.shutdown",
    ]
    assert response["result"]["protocol_version"] == 1
    assert isinstance(response["result"]["ffprobe_available"], bool)


def test_invalid_requests_return_structured_errors() -> None:
    for payload in [
        [],
        {},
        {"version": 2, "id": "x", "method": "health"},
        {"version": 1, "id": "x", "method": "shell.execute"},
        {"version": 1, "id": "x", "method": "media.probe", "params": {}},
    ]:
        response = handle_request(payload)
        assert response["ok"] is False
        assert "error" in response


def test_cli_reads_one_request_per_line() -> None:
    process = subprocess.run(
        [sys.executable, "-m", "catty_engine.ipc"],
        input=(
            json.dumps({"version": 1, "id": "health-1", "method": "health", "params": {}})
            + "\n"
        ),
        capture_output=True,
        text=True,
        check=False,
    )
    assert process.returncode == 0
    response = json.loads(process.stdout.strip())
    assert response["id"] == "health-1"
    assert response["ok"] is True


def test_media_probe_error_is_structured(monkeypatch) -> None:
    def fail_probe(_path: Path):
        raise FFprobeNotFoundError("ffprobe is unavailable")

    monkeypatch.setattr("catty_engine.ipc.probe_media", fail_probe)
    response = handle_request(
        {
            "version": 1,
            "id": "probe-1",
            "method": "media.probe",
            "params": {"path": "/tmp/video.mp4"},
        }
    )
    assert response["ok"] is False
    assert response["error"]["code"] == "FFPROBE_NOT_FOUND"
