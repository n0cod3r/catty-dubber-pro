"""Lazy local-only VoxCPM2 inference. Never downloads weights during synthesis."""
from __future__ import annotations

import contextlib
import logging
import sys
import threading
from pathlib import Path
from typing import Any

from catty_engine.models import ModelManager
from catty_engine.settings.service import SettingsService

logger = logging.getLogger(__name__)
_lock = threading.Lock()
_model: Any = None
_model_key: tuple[str, str] | None = None


class VoxCPM2Provider:
    def synthesize(self, text: str, output: Path, *, reference: Path | None = None,
                   reference_text: str | None = None, style: str = "") -> Path:
        global _model, _model_key
        if not text.strip():
            raise ValueError("Speech text cannot be empty")
        manager = ModelManager()
        if not manager.installed("voxcpm2"):
            raise ValueError("Download VoxCPM2 in Settings → Models before generating a voice.")
        path = manager.path_for("voxcpm2")
        if reference is not None and not reference.is_file():
            raise ValueError("Voice reference audio is missing")
        device = SettingsService().get().performance.device
        key = (str(path), device)
        # Model libraries may print to stdout, which is reserved for engine RPC.
        with _lock, contextlib.redirect_stdout(sys.stderr):
            try:
                import soundfile as sf
                from voxcpm import VoxCPM
            except ImportError as exc:
                raise RuntimeError("VoxCPM2 runtime is missing. Update/sync the Catty engine dependencies.") from exc
            if _model is None or _model_key != key:
                logger.info("Loading VoxCPM2 on %s", device)
                _model = VoxCPM.from_pretrained(str(path), load_denoiser=False,
                    local_files_only=True, optimize=False, device=device)
                _model_key = key
            kwargs: dict[str, Any] = {}
            if reference:
                if reference_text and reference_text.strip():
                    kwargs.update(prompt_wav_path=str(reference), prompt_text=reference_text.strip())
                else:
                    kwargs["reference_wav_path"] = str(reference)
            content = f"({style.strip()}){text.strip()}" if style.strip() else text.strip()
            logger.info("Synthesizing VoxCPM2 speech (%d characters)", len(text))
            audio = _model.generate(text=content, normalize=False, denoise=False,
                cfg_value=2.0, inference_timesteps=10, seed=42, **kwargs)
            import numpy as np
            if np.asarray(audio).size == 0 or not np.isfinite(audio).all():
                raise RuntimeError("VoxCPM2 returned invalid audio")
            output.parent.mkdir(parents=True, exist_ok=True)
            sf.write(str(output), audio, _model.tts_model.sample_rate, format="WAV")
        return output
