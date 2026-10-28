import json
import os
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
        "tts.voices",
        "tts.ensure_voice",
        "tts.preview",
        "tts.generate",
        "tts.library_list",
        "tts.library_create",
        "tts.library_preview",
        "tts.library_remove",
        "tts.library_use",
        "tts.assign_segment_voice",
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


def test_unavailable_keychain_returns_configuration_error(monkeypatch) -> None:
    from catty_engine.settings.credentials import CredentialError, CredentialStore

    def unavailable(*args, **kwargs):
        raise CredentialError("Secure credential storage is unavailable.")

    monkeypatch.setattr(CredentialStore, "set", unavailable)
    response = handle_request(
        {
            "version": 1,
            "id": "credential",
            "method": "settings.credential_add",
            "params": {"provider": "gemini", "secret": "test-key"},
        }
    )
    assert response["error"]["code"] == "CONFIGURATION_ERROR"
    assert "unavailable" in response["error"]["message"]


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


def test_cli_ignores_non_utf8_stdio_environment() -> None:
    # Windows pipes default to the ANSI code page. The engine must always speak
    # UTF-8 so Khmer/Chinese identifiers and paths survive the IPC boundary.
    result = subprocess.run(
        [sys.executable, "-m", "catty_engine", "--rpc"],
        input=json.dumps(
            {"version": 1, "id": "សួស្តី", "method": "health"}, ensure_ascii=False
        ),
        capture_output=True,
        text=True,
        encoding="utf-8",
        env={**os.environ, "PYTHONIOENCODING": "cp1252"},
        check=True,
        timeout=10,
    )
    assert json.loads(result.stdout)["id"] == "សួស្តី"


def test_server_exits_on_shutdown_without_waiting_for_eof() -> None:
    process = subprocess.Popen(
        [sys.executable, "-m", "catty_engine", "--server"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
    )
    assert process.stdin is not None
    assert process.stdout is not None
    process.stdin.write(
        json.dumps({"version": 1, "id": "bye", "method": "system.shutdown"}) + "\n"
    )
    process.stdin.flush()
    response = json.loads(process.stdout.readline())
    assert response["result"] == {"shutting_down": True}
    # Keep stdin open: the host sends shutdown while its pipe is still alive.
    process.wait(timeout=5)
    assert process.returncode == 0


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
        {"version": 1, "id": "bye", "method": "system.shutdown", "params": {}},
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


def test_dialogue_text_command_persists_unicode_and_rejects_stale_text(
    tmp_path: Path,
) -> None:
    from catty_engine.project import DialogueSegment, ProjectService

    service = ProjectService()
    project = service.create_project(tmp_path, "Dialogue")
    episode = project.add_episode(str(tmp_path / "EP01.mp4"))
    segment = DialogueSegment(start=1, end=3, source_language="zh", source_text="你号")
    episode.dialogue_segments = [segment]
    service.save_project(tmp_path, project)
    params = {
        "project_directory": str(tmp_path),
        "episode_id": str(episode.id),
        "segment_id": str(segment.id),
        "text": "你好！",
        "expected_text": "你号",
    }
    response = handle_request(
        {
            "version": 1,
            "id": "edit-text",
            "method": "project.dialogue_update_text",
            "params": params,
        }
    )
    assert "error" not in response
    assert response["result"]["dialogue_segments"][0]["source_text"] == "你好！"
    assert (
        service.open_project(tmp_path).episodes[0].dialogue_segments[0].source_text
        == "你好！"
    )
    stale = handle_request(
        {
            "version": 1,
            "id": "stale-text",
            "method": "project.dialogue_update_text",
            "params": params,
        }
    )
    assert stale["error"]["code"] == "INVALID_REQUEST"
