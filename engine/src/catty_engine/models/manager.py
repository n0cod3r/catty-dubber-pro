"""Downloadable local AI model registry and background installer."""
from __future__ import annotations

import json
import logging
import platform
import shutil
import subprocess
import sys
import tempfile
import threading
from dataclasses import dataclass, field
from pathlib import Path

from huggingface_hub import snapshot_download

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
_REGISTRY = {spec.id: spec for spec in LOCAL_TRANSLATION_MODELS}


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


def _download_command(spec: ModelSpec, staging: Path) -> list[str]:
    """Run snapshot_download out-of-process so Cancel can stop an active HTTP transfer."""
    script = (
        "import json,sys; from huggingface_hub import snapshot_download; "
        "snapshot_download(repo_id=sys.argv[1], local_dir=sys.argv[2], "
        "allow_patterns=json.loads(sys.argv[3]))"
    )
    return [sys.executable, "-c", script, spec.repository, str(staging), json.dumps(spec.allow_patterns)]


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
            logger.info("Model download started: %s (%s)", model_id, spec.repository)
            threading.Thread(target=self._install_worker, args=(model_id,), name=f"catty-model-{model_id}", daemon=True).start()
        return self._snapshot(spec)

    def _install_worker(self, model_id: str) -> None:
        spec = self.spec(model_id)
        target = self.path_for(model_id)
        staging = self.staging_path_for(model_id)
        staging.mkdir(parents=True, exist_ok=True)
        with _JOBS_LOCK:
            job = _JOBS[model_id]
        try:
            # A pipe can deadlock when Hugging Face writes enough progress/error
            # output before the parent reads it. A temporary file has no pipe
            # back-pressure and still lets Catty report the final error line.
            with tempfile.TemporaryFile(mode="w+t", encoding="utf-8") as stderr_file:
                process = subprocess.Popen(
                    _download_command(spec, staging),
                    stdout=subprocess.DEVNULL,
                    stderr=stderr_file,
                    text=True,
                )
                with _JOBS_LOCK:
                    job.process = process
                while process.poll() is None:
                    if job.cancel_event.wait(0.2):
                        logger.info("Stopping model download process: %s", model_id)
                        process.terminate()
                        try:
                            process.wait(timeout=2.0)
                        except subprocess.TimeoutExpired:
                            process.kill()
                            process.wait(timeout=2.0)
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

    def install(self, model_id: str) -> dict[str, object]:
        """Synchronous install retained for callers/tests that need completion."""
        spec = self.spec(model_id)
        target = self.path_for(model_id)
        staging = self.staging_path_for(model_id)
        if self.installed(model_id):
            return self._snapshot(spec)
        staging.mkdir(parents=True, exist_ok=True)
        logger.info("Synchronous model download started: %s", model_id)
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
            else:
                process = None
                _JOBS.pop(model_id, None)
        if job is not None and job.status == "cancelling":
            if process is not None and process.poll() is None:
                logger.info("Cancel requested for model download: %s", model_id)
                process.terminate()
            return self._snapshot(spec)
        logger.info("Removing model data: %s", model_id)
        shutil.rmtree(self.path_for(model_id), ignore_errors=True)
        shutil.rmtree(self.staging_path_for(model_id), ignore_errors=True)
        logger.info("Model data removed: %s", model_id)
        return self._snapshot(spec)
