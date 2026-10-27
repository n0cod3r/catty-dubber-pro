from __future__ import annotations

import os
import shutil
import sys
import tarfile
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any

_RELEASE_ROOT = "https://github.com/k2-fsa/sherpa-onnx/releases/download/asr-models"


@dataclass(frozen=True)
class ArchiveModel:
    directory: str
    archive: str
    model_file: str
    model_name: str


SENSE_SMALL = ArchiveModel(
    directory="sherpa-onnx-sense-voice-zh-en-ja-ko-yue-int8-2024-07-17",
    archive="sherpa-onnx-sense-voice-zh-en-ja-ko-yue-int8-2024-07-17.tar.bz2",
    model_file="model.int8.onnx",
    model_name="sense-voice-small-int8-2024-07-17",
)
SILERO_FILE = "silero_vad.onnx"


class ModelManager:
    """Resolve and lazily install Catty's built-in speech models.

    CATTTY_MODEL_DIR can override the OS cache directory for development/tests.
    Downloads are written to a temporary file and promoted only after extraction,
    so interrupted installs are never treated as ready models.
    """

    def __init__(self, root: Path | None = None) -> None:
        self.root = (root or _default_model_root()).expanduser().resolve()

    def ensure_asr(self, backend_id: str) -> dict[str, Any]:
        if backend_id == "paraformer":
            # Paraformer is provided by FunASR (large model + FSMN-VAD + CT-Punc
            # + CAM++) and is resolved by catty_engine.speakers.funasr. The sherpa
            # Paraformer-small archive must never be downloaded by Smart Transcribe.
            raise ValueError(
                "Paraformer is provided by FunASR; sherpa Paraformer is unavailable"
            )
        if backend_id == "sense-small":
            directory = self._ensure_archive(SENSE_SMALL)
            return {
                "model": str(directory / SENSE_SMALL.model_file),
                "tokens": str(directory / "tokens.txt"),
                "model_name": SENSE_SMALL.model_name,
                "language": "auto",
                "use_itn": True,
                "num_threads": 2,
                "provider": "cpu",
            }
        raise ValueError(f"Unsupported ASR backend: {backend_id}")

    def ensure_vad(self, backend_id: str) -> dict[str, Any]:
        if backend_id != "silero":
            raise ValueError(f"Unsupported VAD backend: {backend_id}")
        self.root.mkdir(parents=True, exist_ok=True)
        target = self.root / "silero" / SILERO_FILE
        if not target.is_file() or target.stat().st_size == 0:
            target.parent.mkdir(parents=True, exist_ok=True)
            self._download(f"{_RELEASE_ROOT}/{SILERO_FILE}", target)
        return {
            "model": str(target),
            "threshold": 0.5,
            "min_silence_duration": 0.20,
            "min_speech_duration": 0.10,
            "max_speech_duration": 30.0,
        }

    def _ensure_archive(self, spec: ArchiveModel) -> Path:
        self.root.mkdir(parents=True, exist_ok=True)
        target = self.root / spec.directory
        model = target / spec.model_file
        tokens = target / "tokens.txt"
        if (
            model.is_file()
            and model.stat().st_size > 0
            and tokens.is_file()
            and tokens.stat().st_size > 0
        ):
            return target

        archive = self.root / spec.archive
        staging = self.root / f".{spec.directory}.installing"
        if staging.exists():
            shutil.rmtree(staging)
        if target.exists():
            shutil.rmtree(target)
        self._download(f"{_RELEASE_ROOT}/{spec.archive}", archive)
        staging.mkdir(parents=True, exist_ok=True)
        try:
            with tarfile.open(archive, "r:bz2") as bundle:
                bundle.extractall(staging, filter="data")
            extracted = staging / spec.directory
            if (
                not (extracted / spec.model_file).is_file()
                or not (extracted / "tokens.txt").is_file()
            ):
                raise RuntimeError(
                    f"Downloaded model archive is incomplete: {spec.directory}"
                )
            os.replace(extracted, target)
        finally:
            archive.unlink(missing_ok=True)
            if staging.exists():
                shutil.rmtree(staging)
        return target

    @staticmethod
    def _download(url: str, target: Path) -> None:
        temporary = target.with_suffix(target.suffix + ".part")
        temporary.unlink(missing_ok=True)
        try:
            request = urllib.request.Request(
                url, headers={"User-Agent": "Catty-Dubber-Pro/0.1"}
            )
            with (
                urllib.request.urlopen(request, timeout=60) as response,
                temporary.open("wb") as output,
            ):
                shutil.copyfileobj(response, output, length=1024 * 1024)
            if temporary.stat().st_size == 0:
                raise RuntimeError(f"Downloaded model is empty: {url}")
            os.replace(temporary, target)
        finally:
            temporary.unlink(missing_ok=True)


def _default_model_root() -> Path:
    override = os.environ.get("CATTY_MODEL_DIR")
    if override:
        return Path(override)
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Caches" / "Catty Dubber Pro" / "models"
    if os.name == "nt":
        base = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
        return base / "Catty Dubber Pro" / "models"
    base = Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache"))
    return base / "catty-dubber-pro" / "models"
