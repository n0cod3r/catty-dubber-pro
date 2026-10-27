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
        "project.import_episode",
        "speech.transcribe",
        "asr.paraformer",
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
        assert handle_request(payload)["error"]["code"] == "INVALID_REQUEST"


def test_missing_file_returns_media_error(tmp_path: Path) -> None:
    response = handle_request(
        {
            "version": 1,
            "id": "missing",
            "method": "media.probe",
            "params": {"path": str(tmp_path / "missing.mp4")},
        }
    )
    assert response["error"]["code"] == "MEDIA_PROBE_FAILED"


def test_missing_ffprobe_has_actionable_error(monkeypatch) -> None:
    def missing(_self, _path):
        raise FFprobeNotFoundError("ffprobe executable not found")

    monkeypatch.setattr("catty_engine.ipc.MediaProbeService.probe", missing)
    response = handle_request(
        {
            "version": 1,
            "id": "probe",
            "method": "media.probe",
            "params": {"path": "/media.mp4"},
        }
    )
    assert response["error"]["code"] == "FFPROBE_NOT_FOUND"


def test_cli_stdout_is_one_json_response() -> None:
    result = subprocess.run(
        [sys.executable, "-m", "catty_engine", "--rpc"],
        input=json.dumps({"version": 1, "id": "សួស្តី", "method": "health"}),
        capture_output=True,
        text=True,
        check=True,
        timeout=10,
    )
    assert json.loads(result.stdout)["id"] == "សួស្តី"
    assert len(result.stdout.splitlines()) == 1


def test_cli_malformed_json_stays_in_protocol() -> None:
    result = subprocess.run(
        [sys.executable, "-m", "catty_engine", "--rpc"],
        input="{broken",
        capture_output=True,
        text=True,
        check=True,
        timeout=10,
    )
    assert json.loads(result.stdout)["error"]["code"] == "INVALID_JSON"


def test_server_handles_multiple_requests_and_shutdown() -> None:
    requests = [
        {"version": 1, "id": "one", "method": "system.hello", "params": {}},
        {"version": 1, "id": "two", "method": "health", "params": {}},
        {
            "version": 1,
            "id": "bye",
            "method": "system.shutdown",
            "params": {},
        },
    ]
    result = subprocess.run(
        [sys.executable, "-m", "catty_engine", "--server"],
        input="".join(json.dumps(request) + "\n" for request in requests),
        capture_output=True,
        text=True,
        check=True,
        timeout=10,
    )
    responses = [json.loads(line) for line in result.stdout.splitlines()]
    assert [response["id"] for response in responses] == ["one", "two", "bye"]
    assert responses[0]["result"]["protocol_version"] == 1
    assert responses[2]["result"] == {"shutting_down": True}
