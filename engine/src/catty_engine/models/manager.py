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
    runtime: str = "m2m100"


@dataclass
class InstallJob:
    status: str = "downloading"
    error: str | None = None


_M2M100_FILES = (
    "config.json", "generation_config.json", "pytorch_model.bin", "model.safetensors",
    "sentencepiece.bpe.model", "special_tokens_map.json", "tokenizer_config.json", "vocab.json",
)

LOCAL_TRANSLATION_MODELS = (
    ModelSpec(id="m2m100-418m", name="M2M100 418M", kind="translation", repository="facebook/m2m100_418M", license="MIT", description="Balanced local model. Direct Chinese → Khmer translation with lower memory use.", approximate_size_mb=1960, allow_patterns=_M2M100_FILES),
    ModelSpec(id="m2m100-1.2b", name="M2M100 1.2B", kind="translation", repository="facebook/m2m100_1.2B", license="MIT", description="Larger local model for users who prefer translation quality over speed and memory use.", approximate_size_mb=4950, allow_patterns=_M2M100_FILES),
)
LOCAL_TRANSLATION_MODEL = LOCAL_TRANSLATION_MODELS[0]
_REGISTRY = {spec.id: spec for spec in LOCAL_TRANSLATION_MODELS}
_JOBS: dict[str, InstallJob] = {}
_JOBS_LOCK = threading.Lock()


class ModelManager:
    def root(self) -> Path:
        path = app_data_dir() / "models"
        path.mkdir(parents=True, exist_ok=True)
        return path

    def path_for(self, model_id: str) -> Path:
        self.spec(model_id)
        return self.root() / model_id

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

    def _job_snapshot(self, model_id: str) -> dict[str, object]:
        with _JOBS_LOCK:
            job = _JOBS.get(model_id)
        if job is None:
            return {"model_id": model_id, "status": "installed" if self.installed(model_id) else "idle", "error": None}
        return {"model_id": model_id, "status": job.status, "error": job.error}

    def _snapshot(self, spec: ModelSpec) -> dict[str, object]:
        path = self.path_for(spec.id)
        installed = self.installed(spec.id)
        job = self._job_snapshot(spec.id)
        return {"id": spec.id, "name": spec.name, "kind": spec.kind, "repository": spec.repository, "license": spec.license, "description": spec.description, "approximate_size_mb": spec.approximate_size_mb, "installed": installed, "path": str(path) if installed else None, "install_status": job["status"], "install_error": job["error"]}

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
            threading.Thread(target=self._install_worker, args=(model_id,), name=f"catty-model-{model_id}", daemon=True).start()
        return self._snapshot(spec)

    def _install_worker(self, model_id: str) -> None:
        spec = self.spec(model_id)
        target = self.path_for(model_id)
        staging = target.with_name(f".{target.name}.downloading")
        staging.mkdir(parents=True, exist_ok=True)
        try:
            snapshot_download(repo_id=spec.repository, local_dir=staging, allow_patterns=list(spec.allow_patterns))
            (staging / ".catty-installed").write_text(spec.repository, encoding="utf-8")
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
        staging = target.with_name(f".{target.name}.downloading")
        if self.installed(model_id):
            return self._snapshot(spec)
        staging.mkdir(parents=True, exist_ok=True)
        snapshot_download(repo_id=spec.repository, local_dir=staging, allow_patterns=list(spec.allow_patterns))
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
        shutil.rmtree(self.path_for(model_id).with_name(f".{model_id}.downloading"), ignore_errors=True)
        return self._snapshot(spec)
