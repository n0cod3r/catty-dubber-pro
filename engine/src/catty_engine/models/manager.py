"""Downloadable local AI model registry and background installer."""
from __future__ import annotations

import shutil
import threading
from dataclasses import dataclass
from pathlib import Path

from huggingface_hub import snapshot_download

from catty_engine.settings.paths import app_data_dir


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
LOCAL_TRANSLATION_MODEL = LOCAL_TRANSLATION_MODELS[0]
_REGISTRY = {spec.id: spec for spec in LOCAL_TRANSLATION_MODELS}
_JOBS: dict[str, InstallJob] = {}
_JOBS_LOCK = threading.Lock()


def _directory_size(path: Path) -> int:
    """Return bytes currently present in a model staging directory.

    Hugging Face writes partial downloads into the local staging tree, so this also
    counts in-progress shard bytes without coupling Catty to downloader internals.
    """
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
        return [
            spec for spec in _REGISTRY.values() if kind is None or spec.kind == kind
        ]

    def _progress_snapshot(self, spec: ModelSpec, status: str) -> dict[str, object]:
        total_bytes = spec.approximate_size_mb * 1024 * 1024
        if status == "installed":
            downloaded_bytes = total_bytes
            progress = 100
        else:
            downloaded_bytes = _directory_size(self.staging_path_for(spec.id))
            progress = min(99, round(downloaded_bytes * 100 / total_bytes)) if total_bytes else 0
        return {
            "downloaded_bytes": downloaded_bytes,
            "total_bytes": total_bytes,
            "progress": progress,
        }

    def _job_snapshot(self, model_id: str) -> dict[str, object]:
        spec = self.spec(model_id)
        with _JOBS_LOCK:
            job = _JOBS.get(model_id)
        if job is None:
            status = "installed" if self.installed(model_id) else "idle"
            result: dict[str, object] = {
                "model_id": model_id,
                "status": status,
                "error": None,
            }
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
        already_running = False
        with _JOBS_LOCK:
            current = _JOBS.get(model_id)
            already_running = current is not None and current.status == "downloading"
            if not already_running:
                _JOBS[model_id] = InstallJob()
        if not already_running:
            threading.Thread(
                target=self._install_worker,
                args=(model_id,),
                name=f"catty-model-{model_id}",
                daemon=True,
            ).start()
        return self._snapshot(spec)

    def _install_worker(self, model_id: str) -> None:
        spec = self.spec(model_id)
        target = self.path_for(model_id)
        staging = self.staging_path_for(model_id)
        staging.mkdir(parents=True, exist_ok=True)
        try:
            snapshot_download(
                repo_id=spec.repository,
                local_dir=staging,
                allow_patterns=list(spec.allow_patterns),
            )
            (staging / ".catty-installed").write_text(
                spec.repository, encoding="utf-8"
            )
            shutil.rmtree(target, ignore_errors=True)
            staging.replace(target)
            with _JOBS_LOCK:
                _JOBS[model_id] = InstallJob(status="installed")
        except Exception as exc:
            # Keep partial files so Hugging Face can resume them on the next install attempt.
            with _JOBS_LOCK:
                _JOBS[model_id] = InstallJob(status="failed", error=str(exc))

    def install(self, model_id: str) -> dict[str, object]:
        """Synchronous install retained for callers/tests that need completion."""
        spec = self.spec(model_id)
        target = self.path_for(model_id)
        staging = self.staging_path_for(model_id)
        if self.installed(model_id):
            return self._snapshot(spec)
        staging.mkdir(parents=True, exist_ok=True)
        snapshot_download(
            repo_id=spec.repository,
            local_dir=staging,
            allow_patterns=list(spec.allow_patterns),
        )
        (staging / ".catty-installed").write_text(spec.repository, encoding="utf-8")
        shutil.rmtree(target, ignore_errors=True)
        staging.replace(target)
        with _JOBS_LOCK:
            _JOBS[model_id] = InstallJob(status="installed")
        return self._snapshot(spec)

    def remove(self, model_id: str) -> dict[str, object]:
        spec = self.spec(model_id)
        with _JOBS_LOCK:
            job = _JOBS.get(model_id)
            if job is not None and job.status == "downloading":
                raise ValueError("Cannot remove a model while it is downloading")
            _JOBS.pop(model_id, None)
        shutil.rmtree(self.path_for(model_id), ignore_errors=True)
        shutil.rmtree(self.staging_path_for(model_id), ignore_errors=True)
        return self._snapshot(spec)
