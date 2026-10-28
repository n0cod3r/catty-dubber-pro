"""Local and configuration-ready translation providers."""
from __future__ import annotations

import platform
from typing import Any

from catty_engine.models import LOCAL_TRANSLATION_MODEL, ModelManager

from ..base import ProviderError
from ..models import (
    ConnectionTestResult,
    TranslationBatchRequest,
    TranslationBatchResult,
    TranslationInput,
    TranslationModel,
    TranslationOutput,
)

# Keep local models warm across TranslationService/provider instances.
_TRANSFORMERS_MODEL_CACHE: dict[str, tuple[Any, Any, str]] = {}
_MLX_MODEL_CACHE: dict[str, tuple[Any, Any]] = {}


def _hy_mt2_prompt(segment: TranslationInput, request: TranslationBatchRequest) -> str:
    """Build an Hy-MT2 translation instruction; context is reference-only."""
    lines: list[str] = []
    if request.use_context and (segment.previous or segment.next):
        lines.append("Use the following dialogue only as context for meaning. Do not translate it:")
        for item in segment.previous:
            speaker = f"{item.speaker}: " if request.use_speaker_context and item.speaker else ""
            lines.append(f"Previous: {speaker}{item.text}")
        for item in segment.next:
            speaker = f"{item.speaker}: " if request.use_speaker_context and item.speaker else ""
            lines.append(f"Next: {speaker}{item.text}")
    if request.glossary:
        lines.append("Reference the following translations exactly when applicable:")
        for term in request.glossary:
            note = f" ({term.note})" if term.note else ""
            lines.append(f"{term.source} translates to {term.target}{note}")
    if request.style == "natural_dubbing":
        lines.append("Use natural spoken Khmer suitable for drama dubbing.")
    elif request.style == "short_conversational":
        lines.append("Use concise, natural conversational Khmer.")
    if request.custom_instructions:
        lines.append(request.custom_instructions.strip())
    if request.use_speaker_context and segment.speaker:
        lines.append(f"Current speaker: {segment.speaker}")
    lines.extend(
        [
            "Translate ONLY the following Current text into Khmer. "
            "Only output the translated result without any additional explanation:",
            f"Current: {segment.text}",
        ]
    )
    return "\n".join(lines)


# Kept as a compatibility alias for tests/extensions that used the old helper name.
_contextual_prompt = _hy_mt2_prompt


def _torch_device() -> str:
    import torch

    if torch.cuda.is_available():
        return "cuda"
    if torch.backends.mps.is_available():
        return "mps"
    return "cpu"


def _load_transformers_model(
    model_id: str, manager: ModelManager
) -> tuple[Any, Any, str]:
    cached = _TRANSFORMERS_MODEL_CACHE.get(model_id)
    if cached is not None:
        return cached
    from transformers import AutoModelForCausalLM, AutoTokenizer

    path = manager.path_for(model_id)
    device = _torch_device()
    tokenizer = AutoTokenizer.from_pretrained(path, local_files_only=True)
    model = AutoModelForCausalLM.from_pretrained(path, local_files_only=True)
    model.to(device)
    model.eval()
    result = (tokenizer, model, device)
    _TRANSFORMERS_MODEL_CACHE[model_id] = result
    return result


def _load_mlx_model(model_id: str, manager: ModelManager) -> tuple[Any, Any]:
    cached = _MLX_MODEL_CACHE.get(model_id)
    if cached is not None:
        return cached
    if platform.system() != "Darwin" or platform.machine() not in {"arm64", "aarch64"}:
        raise ProviderError("Hy-MT2 7B 4-bit requires an Apple Silicon Mac.")
    try:
        from mlx_lm import load
    except ImportError as exc:
        raise ProviderError(
            "Hy-MT2 7B 4-bit requires the Catty MLX runtime (mlx-lm)."
        ) from exc
    model, tokenizer = load(str(manager.path_for(model_id)))
    result = (model, tokenizer)
    _MLX_MODEL_CACHE[model_id] = result
    return result


class LocalProvider:
    """Offline Chinese → Khmer translation using a user-selected Hy-MT2 model."""

    id = "local"

    def __init__(self, selected_model: str | None = None) -> None:
        # Removed/unknown model settings safely migrate to Catty's recommended model.
        candidate = selected_model or LOCAL_TRANSLATION_MODEL.id
        self.manager = ModelManager()
        try:
            self.manager.spec(candidate)
        except ValueError:
            candidate = LOCAL_TRANSLATION_MODEL.id
        self.selected_model = candidate

    def list_models(self) -> list[TranslationModel]:
        return [
            TranslationModel(id=spec.id, name=spec.name, description=spec.description)
            for spec in self.manager.list_specs(kind="translation")
        ]

    def test_connection(self) -> ConnectionTestResult:
        spec = self.manager.spec(self.selected_model)
        if not self.manager.installed(self.selected_model):
            return ConnectionTestResult(
                ok=False, message=f"{spec.name} must be downloaded first."
            )
        if spec.runtime == "hy_mt2_mlx" and (
            platform.system() != "Darwin"
            or platform.machine() not in {"arm64", "aarch64"}
        ):
            return ConnectionTestResult(
                ok=False, message=f"{spec.name} requires an Apple Silicon Mac."
            )
        return ConnectionTestResult(
            ok=True, message=f"{spec.name} is ready for offline translation."
        )

    def _translate_transformers(
        self, request: TranslationBatchRequest
    ) -> TranslationBatchResult:
        import torch

        tokenizer, model, device = _load_transformers_model(
            self.selected_model, self.manager
        )
        outputs: list[TranslationOutput] = []
        for segment in request.segments:
            prompt = _hy_mt2_prompt(segment, request)
            encoded = tokenizer(
                prompt,
                add_special_tokens=False,
                return_tensors="pt",
                truncation=True,
                max_length=2048,
            )
            encoded = {key: value.to(device) for key, value in encoded.items()}
            with torch.inference_mode():
                generated = model.generate(
                    **encoded,
                    do_sample=False,
                    max_new_tokens=256,
                    repetition_penalty=1.05,
                )
            input_length = encoded["input_ids"].shape[1]
            text = tokenizer.decode(
                generated[0][input_length:], skip_special_tokens=True
            ).strip()
            if not text:
                raise ProviderError(
                    f"{self.selected_model} returned an empty translation for {segment.id}."
                )
            outputs.append(TranslationOutput(id=segment.id, text=text))
        return TranslationBatchResult(
            provider=self.id, model=self.selected_model, segments=outputs
        )

    def _translate_mlx(self, request: TranslationBatchRequest) -> TranslationBatchResult:
        try:
            from mlx_lm import generate
        except ImportError as exc:
            raise ProviderError(
                "Hy-MT2 7B 4-bit requires the Catty MLX runtime (mlx-lm)."
            ) from exc

        model, tokenizer = _load_mlx_model(self.selected_model, self.manager)
        outputs: list[TranslationOutput] = []
        for segment in request.segments:
            text = generate(
                model,
                tokenizer,
                prompt=_hy_mt2_prompt(segment, request),
                max_tokens=256,
                verbose=False,
            ).strip()
            if not text:
                raise ProviderError(
                    f"{self.selected_model} returned an empty translation for {segment.id}."
                )
            outputs.append(TranslationOutput(id=segment.id, text=text))
        return TranslationBatchResult(
            provider=self.id, model=self.selected_model, segments=outputs
        )

    def translate_batch(self, request: TranslationBatchRequest) -> TranslationBatchResult:
        if request.source_language != "zh" or request.target_language != "km":
            raise ProviderError(
                "Catty local translation currently supports Chinese → Khmer only."
            )
        if not self.manager.installed(self.selected_model):
            raise ProviderError(
                "Selected local translation model is not installed. Open Settings → Models to download it."
            )
        spec = self.manager.spec(self.selected_model)
        try:
            if spec.runtime == "hy_mt2_transformers":
                return self._translate_transformers(request)
            if spec.runtime == "hy_mt2_mlx":
                return self._translate_mlx(request)
            raise ProviderError(f"Unsupported local translation runtime: {spec.runtime}")
        except ProviderError:
            raise
        except Exception as exc:
            raise ProviderError(f"Local translation failed: {exc}") from exc


class ConfigurationOnlyProvider:
    """Metadata/config foundation for providers implemented in a later milestone."""

    def __init__(self, provider_id: str, name: str) -> None:
        self.id = provider_id
        self.name = name

    def list_models(self) -> list[TranslationModel]:
        raise ProviderError(f"{self.name} model discovery is not available yet.")

    def test_connection(self) -> ConnectionTestResult:
        return ConnectionTestResult(
            ok=False,
            message=f"{self.name} connection testing is not available yet.",
        )

    def translate_batch(self, request: TranslationBatchRequest) -> TranslationBatchResult:
        del request
        raise ProviderError(f"{self.name} translation is not available yet.")
