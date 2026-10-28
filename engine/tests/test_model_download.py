from __future__ import annotations

import hashlib
import http.server
import threading
from dataclasses import replace
from pathlib import Path

import pytest

from catty_engine.models import manager as models
from catty_engine.models.download import download

PAYLOAD = b"catty-model-bytes" * 4096
PAYLOAD_SHA256 = hashlib.sha256(PAYLOAD).hexdigest()


@pytest.fixture
def model_server(tmp_path: Path):
    root = tmp_path / "www"
    root.mkdir()
    (root / "model.onnx").write_bytes(PAYLOAD)

    class Handler(http.server.SimpleHTTPRequestHandler):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, directory=str(root), **kwargs)

        def log_message(self, *args):
            pass

    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}/model.onnx"
    finally:
        server.shutdown()
        thread.join()


def test_download_writes_verified_file(tmp_path: Path, model_server: str) -> None:
    destination = tmp_path / "models" / "model.onnx"

    download(model_server, destination, PAYLOAD_SHA256)

    assert destination.read_bytes() == PAYLOAD


def test_download_rejects_checksum_mismatch(
    tmp_path: Path, model_server: str
) -> None:
    destination = tmp_path / "models" / "model.onnx"

    with pytest.raises(ValueError, match="Checksum mismatch"):
        download(model_server, destination, "0" * 64)

    assert not destination.exists()


def test_url_spec_uses_the_download_module(tmp_path: Path) -> None:
    command = models._download_command(
        models.SEPARATION_MODEL, tmp_path / "staging", token="ownership-token"
    )

    assert command[1:3] == ["-m", "catty_engine.models.download"]
    assert command[3] == models.SEPARATION_MODEL.download_url
    assert command[4] == str(tmp_path / "staging" / models.SEPARATION_MODEL_FILE)
    assert command[5] == models.SEPARATION_MODEL.sha256
    assert command[-1] == "--catty-download-token=ownership-token"


def test_synchronous_install_downloads_url_model(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, model_server: str
) -> None:
    monkeypatch.setenv("CATTY_APP_DATA", str(tmp_path / "app-data"))
    monkeypatch.setattr(models, "_JOBS", {})
    spec = replace(
        models.SEPARATION_MODEL,
        id="test-url-model",
        download_url=model_server,
        sha256=PAYLOAD_SHA256,
    )
    monkeypatch.setitem(models._REGISTRY, spec.id, spec)
    manager = models.ModelManager()

    result = manager.install(spec.id)

    installed = manager.path_for(spec.id) / models.SEPARATION_MODEL_FILE
    assert result["install_status"] == "installed"
    assert result["installed"] is True
    assert installed.read_bytes() == PAYLOAD
    assert manager.installed(spec.id)
