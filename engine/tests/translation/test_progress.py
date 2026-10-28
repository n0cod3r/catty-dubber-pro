import json
import threading

import pytest

from catty_engine.project import DialogueSegment, ProjectService
from catty_engine.settings.models import AppSettings
from catty_engine.translation import service as module
from catty_engine.translation.base import ProviderError
from catty_engine.translation.models import TranslationBatchResult, TranslationOutput
from catty_engine.translation.service import TranslationService


def setup_project(tmp_path, monkeypatch, provider="local"):
    projects = ProjectService()
    project = projects.create_project(tmp_path, "Progress")
    episode = project.add_episode("episode.mp4")
    episode.dialogue_segments = [DialogueSegment(start=i, end=i+1, source_language="zh", source_text=f"你好{i}") for i in range(3)]
    projects.save_project(tmp_path, project)
    settings = AppSettings()
    settings.translation.provider = provider
    monkeypatch.setattr(module.SettingsService, "get", lambda self: settings)
    monkeypatch.setattr(module, "CredentialStore", lambda: object())
    monkeypatch.setattr(module, "CredentialPool", lambda *args: object())
    monkeypatch.setattr(module, "credential_ids", lambda *args: [])
    return projects, episode


def result(request, provider="local"):
    return TranslationBatchResult(provider=provider, model="test", segments=[TranslationOutput(id=s.id, text="សួស្តី") for s in request.segments])


@pytest.mark.parametrize("provider,batch_size,counts", [("local", 12, [1, 2, 3]), ("gemini", 2, [2, 3])])
def test_saved_progress_follows_durable_writes_and_preserves_cloud_batching(tmp_path, monkeypatch, provider, batch_size, counts):
    projects, episode = setup_project(tmp_path, monkeypatch, provider)
    events = []
    def collect(payload):
        if payload["episode"] is not None:
            assert payload["episode"] == projects.open_project(tmp_path).episodes[0].model_dump(mode="json")
        events.append(payload)
    monkeypatch.setattr(module, "emit_translation_progress", collect)
    monkeypatch.setattr(TranslationService, "_translate_batch", staticmethod(lambda p, settings, pool, request: result(request, provider)))
    TranslationService(projects).translate_episode(tmp_path, episode.id, batch_size=batch_size, operation_id="job")
    assert [e["completed"] for e in events if e["phase"] == "saved"] == counts
    assert events[0]["phase"] == "started"
    assert events[-1]["phase"] == "completed"
    assert events[-1]["completed"] == events[-1]["total"] == 3
    assert all(e["operation_id"] == "job" and e["episode_id"] == str(episode.id) for e in events)


def test_partial_success_survives_later_failure(tmp_path, monkeypatch):
    projects, episode = setup_project(tmp_path, monkeypatch)
    calls = 0
    events = []
    def translate(provider, settings, pool, request):
        nonlocal calls
        calls += 1
        if calls == 2:
            raise ProviderError("temporary failure")
        return result(request)
    monkeypatch.setattr(TranslationService, "_translate_batch", staticmethod(translate))
    monkeypatch.setattr(module, "emit_translation_progress", events.append)
    with pytest.raises(ProviderError):
        TranslationService(projects).translate_episode(tmp_path, episode.id, operation_id="job")
    saved = projects.open_project(tmp_path).episodes[0]
    assert saved.dialogue_segments[0].translation.text == "សួស្តី"
    assert saved.dialogue_segments[1].translation is None
    assert events[-1]["phase"] == "failed" and events[-1]["completed"] == 1
    assert events[-1]["episode"]["processing"]["translation"] == "failed"


def test_progress_is_available_while_next_generation_is_still_running(tmp_path, monkeypatch):
    projects, episode = setup_project(tmp_path, monkeypatch)
    waiting, release = threading.Event(), threading.Event()
    events, errors = [], []
    calls = 0
    def translate(provider, settings, pool, request):
        nonlocal calls
        calls += 1
        if calls == 2:
            waiting.set()
            assert release.wait(timeout=5)
        return result(request)
    monkeypatch.setattr(TranslationService, "_translate_batch", staticmethod(translate))
    monkeypatch.setattr(module, "emit_translation_progress", events.append)
    def run():
        try:
            TranslationService(projects).translate_episode(tmp_path, episode.id, operation_id="job")
        except Exception as error:
            errors.append(error)
    worker = threading.Thread(target=run)
    worker.start()
    try:
        assert waiting.wait(timeout=5)
        assert worker.is_alive()
        assert any(e["phase"] == "saved" and e["completed"] == 1 for e in events)
        assert projects.open_project(tmp_path).episodes[0].dialogue_segments[0].translation is not None
    finally:
        release.set()
        worker.join(timeout=5)
    assert not errors and not worker.is_alive()


def test_progress_uses_stderr_and_keeps_full_dialogue(capsys):
    from catty_engine.progress import emit_translation_progress
    payload = {"operation_id": "job", "text": "សួស្តី" * 3000}
    emit_translation_progress(payload)
    captured = capsys.readouterr()
    assert captured.out == ""
    assert json.loads(captured.err)["payload"] == payload
