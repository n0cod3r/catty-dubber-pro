import json
import os
import subprocess
import sys
import time

import pytest

from catty_engine.models import manager as models

MODEL_ID = "voxcpm2"
TOKEN_PREFIX = "--catty-download-token="
SLOW_DOWNLOAD = (
    "import pathlib,sys,time\n"
    "p=pathlib.Path(sys.argv[1])\n"
    "p.mkdir(parents=True, exist_ok=True)\n"
    "for _ in range(1000):\n"
    "    with (p/'chunk.bin').open('ab') as handle:\n"
    "        handle.write(b'x'*65536)\n"
    "    time.sleep(0.02)\n"
)


def _wait_until(predicate, timeout=10.0):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return
        time.sleep(0.02)
    raise AssertionError("condition was not met in time")


def _spawn_download(staging, token):
    return subprocess.Popen(
        [sys.executable, "-c", SLOW_DOWNLOAD, str(staging), f"{TOKEN_PREFIX}{token}"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def _record_download(manager, pid, token):
    manager.download_record_path(MODEL_ID).write_text(
        json.dumps({"pid": pid, "token": token}), encoding="utf-8"
    )


def _record_pid(manager):
    payload = json.loads(manager.download_record_path(MODEL_ID).read_text(encoding="utf-8"))
    return int(payload["pid"])


@pytest.fixture
def manager(tmp_path, monkeypatch):
    monkeypatch.setenv("CATTY_APP_DATA", str(tmp_path))
    monkeypatch.setattr(models, "_JOBS", {})
    yield models.ModelManager()


@pytest.fixture
def fake_download(monkeypatch):
    def command(spec, staging, token=""):
        return [sys.executable, "-c", SLOW_DOWNLOAD, str(staging), f"{TOKEN_PREFIX}{token}"]

    monkeypatch.setattr(models, "_download_command", command)


@pytest.fixture
def orphan(manager):
    children = []

    def start(token="orphaned-download-token"):
        staging = manager.staging_path_for(MODEL_ID)
        child = _spawn_download(staging, token)
        children.append(child)
        _record_download(manager, child.pid, token)
        _wait_until(lambda: models._directory_size(staging) > 0)
        return child

    yield start
    for child in children:
        if child.poll() is None:
            child.kill()
        child.wait()


def test_cancel_stops_active_download_and_keeps_partial_files(manager, fake_download):
    manager.start_install(MODEL_ID)
    staging = manager.staging_path_for(MODEL_ID)
    record = manager.download_record_path(MODEL_ID)
    _wait_until(lambda: record.exists() and models._directory_size(staging) > 0)
    pid = _record_pid(manager)

    result = manager.remove(MODEL_ID)

    assert result["install_status"] in {"cancelling", "cancelled"}
    _wait_until(lambda: not models._pid_alive(pid))
    _wait_until(lambda: manager.install_status(MODEL_ID)[0]["status"] == "cancelled")
    size = models._directory_size(staging)
    time.sleep(0.2)
    assert models._directory_size(staging) == size
    assert staging.exists()
    assert not record.exists()
    assert manager.install_status(MODEL_ID)[0]["downloaded_bytes"] > 0


def test_remove_after_cancel_deletes_partial_files(manager, fake_download):
    manager.start_install(MODEL_ID)
    staging = manager.staging_path_for(MODEL_ID)
    _wait_until(lambda: models._directory_size(staging) > 0)
    manager.remove(MODEL_ID)
    _wait_until(lambda: manager.install_status(MODEL_ID)[0]["status"] == "cancelled")

    result = manager.remove(MODEL_ID)

    assert result["install_status"] == "idle"
    assert result["downloaded_bytes"] == 0
    assert not staging.exists()


def test_remove_stops_download_orphaned_by_previous_engine(manager, orphan):
    child = orphan()
    staging = manager.staging_path_for(MODEL_ID)
    assert manager.install_status(MODEL_ID)[0]["status"] == "downloading"

    result = manager.remove(MODEL_ID)

    assert result["install_status"] == "cancelled"
    _wait_until(lambda: not models._pid_alive(child.pid))
    size = models._directory_size(staging)
    time.sleep(0.2)
    assert models._directory_size(staging) == size
    assert staging.exists()
    assert not manager.download_record_path(MODEL_ID).exists()

    assert manager.remove(MODEL_ID)["install_status"] == "idle"
    assert not staging.exists()


def test_start_install_stops_orphan_before_resuming(manager, fake_download, orphan):
    child = orphan()

    manager.start_install(MODEL_ID)

    assert not models._pid_alive(child.pid)
    record = manager.download_record_path(MODEL_ID)
    _wait_until(lambda: record.exists() and _record_pid(manager) != child.pid)

    manager.remove(MODEL_ID)
    _wait_until(lambda: manager.install_status(MODEL_ID)[0]["status"] == "cancelled")
    manager.remove(MODEL_ID)
    assert not manager.staging_path_for(MODEL_ID).exists()


@pytest.mark.skipif(os.name == "nt", reason="pid ownership check uses ps")
def test_stale_record_never_kills_an_unrelated_process(manager):
    staging = manager.staging_path_for(MODEL_ID)
    staging.mkdir(parents=True)
    (staging / "chunk.bin").write_bytes(b"partial")
    _record_download(manager, os.getpid(), "a-token-this-process-does-not-carry")

    result = manager.remove(MODEL_ID)

    assert result["install_status"] == "idle"
    assert not staging.exists()
    assert not manager.download_record_path(MODEL_ID).exists()
