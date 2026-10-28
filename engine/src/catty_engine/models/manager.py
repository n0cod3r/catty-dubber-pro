"""Downloadable local AI model registry and installer."""
from __future__ import annotations

import shutil
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


LOCAL_TRANSLATION_MODEL = ModelSpec(
    id="m2m100-418m",
    name="M2M100 418M",
    kind="translation",
    repository="facebook/m2m100_418M",
    license="MIT",
    description="Offline multilingual translation with direct Chinese → Khmer support.",
    approximate_size_mb=1960,
    allow_patterns=(
        "config.json",
        "generation_config.json",
        "pytorch_model.bin",
        "sentencepiece.bpe.model",
        "special_tokens_map.json",
        "tokenizer_config.json",
        "vocab.json",
    ),
)

_REGISTRY = {LOCAL_TRANSLATION_MODEL.id: LOCAL_TRANSLATION_MODEL}


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
        path = self.path_for(model_id)
        return (path / ".catty-installed").exists()

    def list_models(self) -> list[dict[str, object]]:
        return [self._snapshot(spec) for spec in _REGISTRY.values()]

    def _snapshot(self, spec: ModelSpec) -> dict[str, object]:
        path = self.path_for(spec.id)
        return {
            "id": spec.id,
            "name": spec.name,
            "kind": spec.kind,
            "repository": spec.repository,
            "license": spec.license,
            "description": spec.description,
            "approximate_size_mb": spec.approximate_size_mb,
            "installed": self.installed(spec.id),
            "path": str(path) if self.installed(spec.id) else None,
        }

    def install(self, model_id: str) -> dict[str, object]:
        spec = self.spec(model_id)
        target = self.path_for(model_id)
        staging = target.with_name(f".{target.name}.downloading")
        if self.installed(model_id):
            return self._snapshot(spec)
        shutil.rmtree(staging, ignore_errors=True)
        staging.mkdir(parents=True, exist_ok=True)
        try:
            snapshot_download(
                repo_id=spec.repository,
                local_dir=staging,
                allow_patterns=list(spec.allow_patterns),
            )
            (staging / ".catty-installed").write_text(spec.repository, encoding="utf-8")
            shutil.rmtree(target, ignore_errors=True)
            staging.replace(target)
        except Exception:
            shutil.rmtree(staging, ignore_errors=True)
            raise
        return self._snapshot(spec)

    def remove(self, model_id: str) -> dict[str, object]:
        spec = self.spec(model_id)
        shutil.rmtree(self.path_for(model_id), ignore_errors=True)
        return self._snapshot(spec)
