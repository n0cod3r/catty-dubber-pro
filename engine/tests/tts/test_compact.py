import io
import json
import threading
import urllib.error
import urllib.request
import wave
from types import SimpleNamespace

import pytest

from catty_engine.tts import compact
from catty_engine.tts.voxcpm import select_runtime


def wave_bytes(rate=48000):
    result = io.BytesIO()
    with wave.open(result, "wb") as stream:
        stream.setnchannels(1)
        stream.setsampwidth(2)
        stream.setframerate(rate)
        stream.writeframes(b"\0\0" * rate)
    return result.getvalue()


def test_wave_validation_rejects_wrong_rate_and_truncation():
    compact.validate_wave(wave_bytes())
    with pytest.raises(ValueError, match="48 kHz"):
        compact.validate_wave(wave_bytes(16000))
    with pytest.raises(ValueError, match="incomplete"):
        compact.validate_wave(wave_bytes()[:-20])


def test_compact_bridge_only_serves_named_assets_and_saves_validated_audio(tmp_path, monkeypatch):
    root = tmp_path / "model"
    root.mkdir()
    (root / "manifest.json").write_text(json.dumps({"version": "test", "files": [{"path": "graph.onnx"}]}))
    (root / "graph.onnx").write_bytes(b"graph")
    monkeypatch.setattr(compact, "ModelManager", lambda: SimpleNamespace(installed=lambda _: True, path_for=lambda _: root))
    monkeypatch.setattr(compact, "text_tokens", lambda *_: [59320, 101])
    errors = []
    audio = wave_bytes()
    threads = []
    def emit(kind, payload):
        assert kind == "compact-inference"
        def client():
            try:
                url = payload["url"]
                with urllib.request.urlopen(urllib.request.Request(url + "accepted", method="POST")) as response:
                    assert response.status == 200
                with urllib.request.urlopen(url + "graph.onnx") as response:
                    assert response.read() == b"graph"
                for suffix in ("../secret", "anything-else"):
                    with pytest.raises(urllib.error.HTTPError):
                        urllib.request.urlopen(url + suffix)
                with pytest.raises(urllib.error.HTTPError) as forbidden:
                    urllib.request.urlopen(urllib.request.Request(url + "graph.onnx", headers={"Origin": "https://unrelated.example"}))
                assert forbidden.value.code == 404
                with urllib.request.urlopen(urllib.request.Request(url + "result", data=audio, method="POST")) as response:
                    assert response.status == 200
            except BaseException as exc:
                errors.append(exc)
                urllib.request.urlopen(urllib.request.Request(payload["url"] + "error", data=str(exc).encode(), method="POST")).close()
        thread = threading.Thread(target=client)
        threads.append(thread)
        thread.start()
    monkeypatch.setattr(compact, "_emit", emit)
    output = tmp_path / "generated.wav"
    compact.CompactVoxCPM2Provider().synthesize("សួស្តី", output)
    for thread in threads:
        thread.join()
    assert not errors
    assert output.read_bytes() == audio


def test_worker_error_never_overwrites_existing_audio(tmp_path, monkeypatch):
    root = tmp_path / "model"
    root.mkdir()
    (root / "manifest.json").write_text(json.dumps({"version": "test", "files": []}))
    monkeypatch.setattr(compact, "ModelManager", lambda: SimpleNamespace(installed=lambda _: True, path_for=lambda _: root))
    monkeypatch.setattr(compact, "text_tokens", lambda *_: [1, 101])
    def emit(_kind, payload):
        urllib.request.urlopen(urllib.request.Request(payload["url"] + "accepted", method="POST")).close()
        urllib.request.urlopen(urllib.request.Request(payload["url"] + "error", data=b"GPU unavailable", method="POST")).close()
    monkeypatch.setattr(compact, "_emit", emit)
    output = tmp_path / "existing.wav"
    output.write_bytes(b"old audio")
    with pytest.raises(RuntimeError, match="GPU unavailable"):
        compact.CompactVoxCPM2Provider().synthesize("សួស្តី", output)
    assert output.read_bytes() == b"old audio"


def test_compact_model_requires_an_explicit_download(monkeypatch, tmp_path):
    monkeypatch.setattr(compact, "ModelManager", lambda: SimpleNamespace(installed=lambda _: False))
    with pytest.raises(ValueError, match="Download"):
        compact.CompactVoxCPM2Provider().synthesize("សួស្តី", tmp_path / "out.wav")
    assert not (tmp_path / "out.wav").exists()


def test_compact_runtime_is_opt_in_when_pytorch_is_installed():
    assert select_runtime("voxcpm2", pytorch_installed=True, compact_installed=True) == "pytorch"
    assert select_runtime("VoxCPM2", pytorch_installed=True, compact_installed=True) == "pytorch"
    assert select_runtime("voxcpm2-compact", pytorch_installed=True, compact_installed=True) == "compact"


def test_missing_pytorch_falls_back_to_compact_only_when_installed():
    assert select_runtime("voxcpm2", pytorch_installed=False, compact_installed=True) == "compact"
    assert select_runtime("VoxCPM2", pytorch_installed=False, compact_installed=True) == "compact"
    assert select_runtime("voxcpm2", pytorch_installed=False, compact_installed=False) == "pytorch"
