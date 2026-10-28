"""Downloadable local AI model registry and background installer."""
from __future__ import annotations

import json
import logging
import os
import platform
import shutil
import signal
import subprocess
import sys
import tempfile
import threading
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path

from huggingface_hub import snapshot_download

from catty_engine.models.download import download
from catty_engine.settings.paths import app_data_dir

logger = logging.getLogger("catty_engine.models")


@dataclass(frozen=True)
class ModelSpec:
    id: str
    name: str
    kind: str
    repository: str
    license: str
    description: str
    approximate_size_mb: int
    allow_patterns: tuple[str, ...]
    runtime: str
    # Release-hosted weights are fetched directly instead of through the Hub.
    download_url: str | None = None
    sha256: str | None = None
    file_name: str | None = None


@dataclass
class InstallJob:
    status: str = "downloading"
    error: str | None = None
    cancel_event: threading.Event = field(default_factory=threading.Event, repr=False)
    process: subprocess.Popen[str] | None = field(default=None, repr=False)


_HY_MT2_FILES = (
    "config.json",
    "generation_config.json",
    "model*.safetensors",
    "model*.safetensors.index.json",
    "tokenizer.json",
    "tokenizer.model",
    "tokenizer_config.json",
    "special_tokens_map.json",
    "chat_template.jinja",
)
_HY_MT2_MLX_FILES = _HY_MT2_FILES + ("mlx_manifest.json",)

LOCAL_TRANSLATION_MODELS = (
    ModelSpec(
        id="hy-mt2-7b-q4",
        name="Hy-MT2 7B 4-bit (Quality)",
        kind="translation",
        repository="mlx-community/Hy-MT2-7B-4bit",
        license="Apache-2.0",
        description=(
            "Recommended high-quality Chinese to Khmer translator for Apple Silicon. "
            "Uses MLX/Metal with 4-bit weights."
        ),
        approximate_size_mb=4240,
        allow_patterns=_HY_MT2_MLX_FILES,
        runtime="hy_mt2_mlx",
    ),
    ModelSpec(
        id="hy-mt2-1.8b",
        name="Hy-MT2 1.8B (Lightweight)",
        kind="translation",
        repository="tencent/Hy-MT2-1.8B",
        license="Apache-2.0",
        description=(
            "Smaller cross-platform Chinese to Khmer translator. Faster to deploy, with a "
            "quality trade-off compared with the recommended 7B model."
        ),
        approximate_size_mb=4090,
        allow_patterns=_HY_MT2_FILES,
        runtime="hy_mt2_transformers",
    ),
)
VOXCPM2_MODEL = ModelSpec(
    id="voxcpm2", name="VoxCPM2 · Voice cloning", kind="tts",
    repository="openbmb/VoxCPM2", license="Apache-2.0",
    description="Local Khmer speech, voice design and reference-audio cloning. Uses PyTorch on CUDA, Apple MPS or CPU.",
    approximate_size_mb=5500,
    allow_patterns=("config.json", "model.safetensors", "audiovae.pth", "tokenizer*.json", "special_tokens_map.json", "tokenization_voxcpm2.py"),
    runtime="voxcpm2",
)
VOXCPM2_COMPACT_MODEL = ModelSpec(
    id="voxcpm2-compact", name="VoxCPM2 Compact · 1.94 GB", kind="tts",
    repository="Uddom/voxcpm2-khmer-webgpu", license="Apache-2.0",
    description="Q4/F16 ONNX voice cloning in Catty's WebGPU worker. Requires a float16-capable WebGPU device. Model files stay in Catty's managed folder.",
    approximate_size_mb=1848,
    allow_patterns=("manifest.json", "q4f16/*.onnx*", "vae/*.onnx*", "embed_tokens.f16.bin", "tokenizer*.json", "special_tokens_map.json", "LICENSE", "NOTICE"),
    runtime="voxcpm2_webgpu",
)
SEPARATION_MODEL_ID = "uvr-mdx-inst-hq3"
SEPARATION_MODEL_FILE = "UVR-MDX-NET-Inst_HQ_3.onnx"
SEPARATION_MODEL = ModelSpec(
    id=SEPARATION_MODEL_ID,
    name="UVR MDX-Net · Dialogue removal",
    kind="separation",
    repository="TRvlvr/model_repo",
    license="UVR public model",
    description=(
        "Separates the original speaker from music and effects so dubbed dialogue can "
        "replace the voice track. Runs on CPU with ONNX Runtime."
    ),
    approximate_size_mb=64,
    allow_patterns=(),
    runtime="mdx_onnx",
    download_url=(
        "https://github.com/TRvlvr/model_repo/releases/download/all_public_uvr_models/"
        f"{SEPARATION_MODEL_FILE}"
    ),
    sha256="317554b07fe1ea5279a77f2b1520a41ea4b93432560c4ffd08792c30fddf9adc",
    file_name=SEPARATION_MODEL_FILE,
)
_REGISTRY = {
    spec.id: spec
    for spec in (
        *LOCAL_TRANSLATION_MODELS,
        VOXCPM2_MODEL,
        VOXCPM2_COMPACT_MODEL,
        SEPARATION_MODEL,
    )
}


def preferred_local_translation_model() -> ModelSpec:
    """Choose a usable default instead of silently selecting an Apple-only runtime."""
    if platform.system() == "Darwin" and platform.machine() in {"arm64", "aarch64"}:
        return _REGISTRY["hy-mt2-7b-q4"]
    return _REGISTRY["hy-mt2-1.8b"]


LOCAL_TRANSLATION_MODEL = preferred_local_translation_model()
_JOBS: dict[str, InstallJob] = {}
_JOBS_LOCK = threading.Lock()


def _directory_size(path: Path) -> int:
    if not path.exists():
        return 0
    total = 0
    for item in path.rglob("*"):
        if not item.is_file() or item.name == ".catty-installed":
            continue
        try:
            total += item.stat().st_size
        except OSError:
            continue
    return total


def _download_command(spec: ModelSpec, staging: Path, token: str = "") -> list[str]:
    """Run the download out-of-process so Cancel can stop an active HTTP transfer."""
    if spec.download_url is not None:
        if not spec.file_name or not spec.sha256:
            raise ValueError(f"Model {spec.id} needs file_name and sha256 for direct download")
        command = [
            sys.executable,
            "-m",
            "catty_engine.models.download",
            spec.download_url,
            str(staging / spec.file_name),
            spec.sha256,
        ]
        if token:
            command.append(f"--catty-download-token={token}")
        return command
    script = (
        "import json,sys; from huggingface_hub import snapshot_download; "
        "snapshot_download(repo_id=sys.argv[1], local_dir=sys.argv[2], "
        "allow_patterns=json.loads(sys.argv[3]))"
    )
    command = [sys.executable, "-c", script, spec.repository, str(staging), json.dumps(spec.allow_patterns)]
    if token:
        command.append(f"--catty-download-token={token}")
    return command


def _pid_alive(pid: int) -> bool:
    """A zombie still accepts signal 0, but it is no longer transferring bytes."""
    if os.name == "nt":
        try:
            output = subprocess.run(
                ["tasklist", "/FI", f"PID eq {pid}", "/NH"],
                capture_output=True, text=True, timeout=5,
            )
        except (OSError, subprocess.SubprocessError):
            return True
        for line in output.stdout.splitlines():
            columns = line.split()
            if len(columns) >= 2 and columns[1] == str(pid):
                return True
        return False
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    stat = Path(f"/proc/{pid}/stat")
    if stat.exists():
        try:
            return stat.read_text(encoding="utf-8").split()[2] != "Z"
        except (OSError, IndexError):
            return True
    if sys.platform == "darwin":
        try:
            output = subprocess.run(
                ["ps", "-p", str(pid), "-o", "stat="],
                capture_output=True, text=True, timeout=5,
            )
        except (OSError, subprocess.SubprocessError):
            return True
        status = output.stdout.strip()
        return bool(status) and not status.startswith("Z")
    return True


def _process_command(pid: int) -> str | None:
    proc = Path(f"/proc/{pid}/cmdline")
    if proc.exists():
        try:
            return proc.read_bytes().replace(b"\0", b" ").decode("utf-8", "replace")
        except OSError:
            return None
    if os.name == "nt":
        return None
    try:
        output = subprocess.run(
            ["ps", "-ww", "-p", str(pid), "-o", "command="],
            capture_output=True, text=True, timeout=5,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    return output.stdout.strip() or None


def _stop_process(process: subprocess.Popen[str]) -> None:
    if process.poll() is not None:
        process.wait()
        return
    process.terminate()
    try:
        process.wait(timeout=2.0)
    except subprocess.TimeoutExpired:
        process.kill()
        try:
            process.wait(timeout=2.0)
        except subprocess.TimeoutExpired:
            logger.warning("Model downloader %s did not exit after SIGKILL", process.pid)


def _stop_pid(pid: int, token: str) -> bool:
    """Stop a recorded downloader; refuse to kill a recycled pid owned by someone else."""
    if not _pid_alive(pid):
        return True
    command = _process_command(pid)
    if command is not None and token not in command:
        return False
    if command is None and os.name != "nt":
        return False
    if os.name == "nt":
        try:
            subprocess.run(
                ["taskkill", "/PID", str(pid), "/T", "/F"],
                capture_output=True, timeout=10,
            )
        except (OSError, subprocess.SubprocessError):
            return False
        return not _pid_alive(pid)
    for sig in (signal.SIGTERM, signal.SIGKILL):
        try:
            os.kill(pid, sig)
        except ProcessLookupError:
            return True
        deadline = time.monotonic() + 2.0
        while time.monotonic() < deadline:
            if not _pid_alive(pid):
                return True
            time.sleep(0.05)
    return not _pid_alive(pid)


class ModelManager:
    def root(self) -> Path:
        path = app_data_dir() / "models"
        path.mkdir(parents=True, exist_ok=True)
        return path

    def path_for(self, model_id: str) -> Path:
        self.spec(model_id)
        return self.root() / model_id

    def staging_path_for(self, model_id: str) -> Path:
        target = self.path_for(model_id)
        return target.with_name(f".{target.name}.downloading")

    def download_record_path(self, model_id: str) -> Path:
        """Outlive the engine process so a restarted engine can stop its downloader."""
        self.spec(model_id)
        return self.root() / f".{model_id}.download.json"

    def _stale_download(self, model_id: str) -> tuple[int, str] | None:
        record = self.download_record_path(model_id)
        try:
            data = json.loads(record.read_text(encoding="utf-8"))
            pid, token = int(data["pid"]), str(data["token"])
        except (OSError, ValueError, KeyError, TypeError):
            record.unlink(missing_ok=True)
            return None
        if not _pid_alive(pid):
            record.unlink(missing_ok=True)
            return None
        command = _process_command(pid)
        if command is not None and token not in command:
            record.unlink(missing_ok=True)
            return None
        return pid, token

    def _stop_stale_download(self, model_id: str) -> bool:
        stale = self._stale_download(model_id)
        if stale is None:
            return False
        logger.info("Stopping orphaned model download: %s", model_id)
        stopped = _stop_pid(*stale)
        self.download_record_path(model_id).unlink(missing_ok=True)
        return stopped

    def spec(self, model_id: str) -> ModelSpec:
        try:
            return _REGISTRY[model_id]
        except KeyError as exc:
            raise ValueError(f"Unknown Catty model: {model_id}") from exc

    def installed(self, model_id: str) -> bool:
        return (self.path_for(model_id) / ".catty-installed").exists()

    def list_models(self) -> list[dict[str, object]]:
        return [self._snapshot(spec) for spec in _REGISTRY.values()]

    def list_specs(self, *, kind: str | None = None) -> list[ModelSpec]:
        return [spec for spec in _REGISTRY.values() if kind is None or spec.kind == kind]

    def _progress_snapshot(self, spec: ModelSpec, status: str) -> dict[str, object]:
        total_bytes = spec.approximate_size_mb * 1024 * 1024
        if status == "installed":
            downloaded_bytes = total_bytes
            progress = 100
        else:
            downloaded_bytes = _directory_size(self.staging_path_for(spec.id))
            progress = min(99, round(downloaded_bytes * 100 / total_bytes)) if total_bytes else 0
        return {"downloaded_bytes": downloaded_bytes, "total_bytes": total_bytes, "progress": progress}

    def _job_snapshot(self, model_id: str) -> dict[str, object]:
        spec = self.spec(model_id)
        with _JOBS_LOCK:
            job = _JOBS.get(model_id)
        if job is None:
            if self._stale_download(model_id) is not None:
                # A downloader left behind by a previous engine is still writing.
                status = "downloading"
            else:
                status = "installed" if self.installed(model_id) else "idle"
            result: dict[str, object] = {"model_id": model_id, "status": status, "error": None}
        else:
            status = job.status
            result = {"model_id": model_id, "status": status, "error": job.error}
        result.update(self._progress_snapshot(spec, status))
        return result

    def _snapshot(self, spec: ModelSpec) -> dict[str, object]:
        path = self.path_for(spec.id)
        installed = self.installed(spec.id)
        job = self._job_snapshot(spec.id)
        return {
            "id": spec.id,
            "name": spec.name,
            "kind": spec.kind,
            "repository": spec.repository,
            "license": spec.license,
            "description": spec.description,
            "approximate_size_mb": spec.approximate_size_mb,
            "installed": installed,
            "path": str(path) if installed else None,
            "install_status": job["status"],
            "install_error": job["error"],
            "downloaded_bytes": job["downloaded_bytes"],
            "total_bytes": job["total_bytes"],
            "download_progress": job["progress"],
        }

    def install_status(self, model_id: str | None = None) -> list[dict[str, object]]:
        if model_id is not None:
            self.spec(model_id)
            return [self._job_snapshot(model_id)]
        return [self._job_snapshot(spec.id) for spec in _REGISTRY.values()]

    def start_install(self, model_id: str) -> dict[str, object]:
        spec = self.spec(model_id)
        if self.installed(model_id):
            return self._snapshot(spec)
        with _JOBS_LOCK:
            current = _JOBS.get(model_id)
            already_running = current is not None and current.status in {"downloading", "cancelling"}
            if not already_running:
                _JOBS[model_id] = InstallJob()
        if not already_running:
            # Two snapshot_download processes on one staging directory corrupt
            # each other, so never resume until the previous child is gone.
            self._stop_stale_download(model_id)
            logger.info("Model download started: %s (%s)", model_id, spec.repository)
            threading.Thread(target=self._install_worker, args=(model_id,), name=f"catty-model-{model_id}", daemon=True).start()
        return self._snapshot(spec)

    def _install_worker(self, model_id: str) -> None:
        spec = self.spec(model_id)
        target = self.path_for(model_id)
        staging = self.staging_path_for(model_id)
        staging.mkdir(parents=True, exist_ok=True)
        record = self.download_record_path(model_id)
        with _JOBS_LOCK:
            job = _JOBS[model_id]
        try:
            # A pipe can deadlock when Hugging Face writes enough progress/error
            # output before the parent reads it. A temporary file has no pipe
            # back-pressure and still lets Catty report the final error line.
            with tempfile.TemporaryFile(mode="w+t", encoding="utf-8") as stderr_file:
                token = uuid.uuid4().hex
                process = subprocess.Popen(
                    _download_command(spec, staging, token),
                    stdout=subprocess.DEVNULL,
                    stderr=stderr_file,
                    text=True,
                )
                record.write_text(
                    json.dumps({"pid": process.pid, "token": token}), encoding="utf-8"
                )
                with _JOBS_LOCK:
                    job.process = process
                while process.poll() is None:
                    if job.cancel_event.wait(0.2):
                        logger.info("Stopping model download process: %s", model_id)
                        _stop_process(process)
                        with _JOBS_LOCK:
                            _JOBS[model_id] = InstallJob(status="cancelled")
                        logger.info("Model download cancelled: %s; partial files kept for resume", model_id)
                        return
                stderr_file.seek(0)
                stderr = stderr_file.read()
                if process.returncode != 0:
                    message = stderr.strip().splitlines()[-1] if stderr.strip() else f"download process exited {process.returncode}"
                    raise RuntimeError(message)
            if job.cancel_event.is_set():
                with _JOBS_LOCK:
                    _JOBS[model_id] = InstallJob(status="cancelled")
                logger.info("Model download cancelled: %s; partial files kept for resume", model_id)
                return
            (staging / ".catty-installed").write_text(spec.repository, encoding="utf-8")
            shutil.rmtree(target, ignore_errors=True)
            staging.replace(target)
            with _JOBS_LOCK:
                _JOBS[model_id] = InstallJob(status="installed")
            logger.info("Model download installed: %s", model_id)
        except Exception as exc:
            if job.cancel_event.is_set():
                with _JOBS_LOCK:
                    _JOBS[model_id] = InstallJob(status="cancelled")
                logger.info("Model download cancelled: %s; partial files kept for resume", model_id)
            else:
                with _JOBS_LOCK:
                    _JOBS[model_id] = InstallJob(status="failed", error=str(exc))
                logger.exception("Model download failed: %s", model_id)
        finally:
            record.unlink(missing_ok=True)

    def install(self, model_id: str) -> dict[str, object]:
        """Synchronous install retained for callers/tests that need completion."""
        spec = self.spec(model_id)
        target = self.path_for(model_id)
        staging = self.staging_path_for(model_id)
        if self.installed(model_id):
            return self._snapshot(spec)
        self._stop_stale_download(model_id)
        staging.mkdir(parents=True, exist_ok=True)
        logger.info("Synchronous model download started: %s", model_id)
        if spec.download_url is not None:
            if not spec.file_name or not spec.sha256:
                raise ValueError(f"Model {spec.id} needs file_name and sha256 for direct download")
            download(spec.download_url, staging / spec.file_name, spec.sha256)
        else:
            snapshot_download(repo_id=spec.repository, local_dir=staging, allow_patterns=list(spec.allow_patterns))
        (staging / ".catty-installed").write_text(spec.repository, encoding="utf-8")
        shutil.rmtree(target, ignore_errors=True)
        staging.replace(target)
        with _JOBS_LOCK:
            _JOBS[model_id] = InstallJob(status="installed")
        logger.info("Synchronous model download installed: %s", model_id)
        return self._snapshot(spec)

    def remove(self, model_id: str) -> dict[str, object]:
        """Cancel an active download, otherwise remove installed/partial model data."""
        spec = self.spec(model_id)
        with _JOBS_LOCK:
            job = _JOBS.get(model_id)
            if job is not None and job.status in {"downloading", "cancelling"}:
                job.status = "cancelling"
                job.cancel_event.set()
                process = job.process
                active = True
            else:
                process = None
                active = False
                _JOBS.pop(model_id, None)
        if active:
            logger.info("Cancel requested for model download: %s", model_id)
            if process is not None:
                _stop_process(process)
            self._stop_stale_download(model_id)
            with _JOBS_LOCK:
                current = _JOBS.get(model_id)
                if current is not None and current.status == "downloading":
                    current.status = "cancelled"
            return self._snapshot(spec)
        if self._stop_stale_download(model_id):
            # A downloader from a previous engine was still writing; keep its
            # partial files so the next Remove can delete them safely.
            with _JOBS_LOCK:
                _JOBS[model_id] = InstallJob(status="cancelled")
            return self._snapshot(spec)
        logger.info("Removing model data: %s", model_id)
        shutil.rmtree(self.path_for(model_id), ignore_errors=True)
        shutil.rmtree(self.staging_path_for(model_id), ignore_errors=True)
        self.download_record_path(model_id).unlink(missing_ok=True)
        logger.info("Model data removed: %s", model_id)
        return self._snapshot(spec)
