"""Local and configuration-ready translation providers."""
from __future__ import annotations

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

# Keep large local models warm across TranslationService/provider instances.
_CAUSAL_MODEL_CACHE: dict[str, tuple[Any, Any]] = {}


def _contextual_prompt(
    segment: TranslationInput, request: TranslationBatchRequest
) -> str:
    lines: list[str] = []
    if request.use_context and (segment.previous or segment.next):
        lines.append("Dialogue context for meaning only. Do not translate these context lines:")
        for item in segment.previous:
            speaker = f"{item.speaker}: " if request.use_speaker_context and item.speaker else ""
            lines.append(f"Previous: {speaker}{item.text}")
        for item in segment.next:
            speaker = f"{item.speaker}: " if request.use_speaker_context and item.speaker else ""
            lines.append(f"Next: {speaker}{item.text}")
        lines.append("Translate only the Current line below.")
    if request.glossary:
        lines.append("Use this glossary when applicable:")
        for term in request.glossary:
            note = f" ({term.note})" if term.note else ""
            lines.append(f"{term.source} -> {term.target}{note}")
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
            "Translate this from Chinese (Simplified) to Khmer:",
            f"Chinese (Simplified): {segment.text}",
            "Khmer:",
        ]
    )
    return "\n".join(lines)


def _load_causal_model(model_id: str, manager: ModelManager) -> tuple[Any, Any]:
    cached = _CAUSAL_MODEL_CACHE.get(model_id)
    if cached is not None:
        return cached
    from transformers import AutoModelForCausalLM, AutoTokenizer

    path = manager.path_for(model_id)
    tokenizer = AutoTokenizer.from_pretrained(path, local_files_only=True)
    model = AutoModelForCausalLM.from_pretrained(path, local_files_only=True)
    model.eval()
    _CAUSAL_MODEL_CACHE[model_id] = (tokenizer, model)
    return tokenizer, model


class LocalProvider:
    """Offline Chinese → Khmer translation using a user-selected local model."""

    id = "local"

    def __init__(self, selected_model: str | None = None) -> None:
        self.selected_model = selected_model or LOCAL_TRANSLATION_MODEL.id
        self.manager = ModelManager()

    def list_models(self) -> list[TranslationModel]:
        return [
            TranslationModel(id=spec.id, name=spec.name, description=spec.description)
            for spec in self.manager.list_specs(kind="translation")
        ]

    def test_connection(self) -> ConnectionTestResult:
        try:
            spec = self.manager.spec(self.selected_model)
        except ValueError as exc:
            return ConnectionTestResult(ok=False, message=str(exc))
        installed = self.manager.installed(self.selected_model)
        return ConnectionTestResult(
            ok=installed,
            message=(
                f"{spec.name} is ready for offline translation."
                if installed
                else f"{spec.name} must be downloaded first."
            ),
        )

    def _translate_m2m100(
        self, request: TranslationBatchRequest
    ) -> TranslationBatchResult:
        from transformers import M2M100ForConditionalGeneration, M2M100Tokenizer

        path = self.manager.path_for(self.selected_model)
        tokenizer = M2M100Tokenizer.from_pretrained(path, local_files_only=True)
        model = M2M100ForConditionalGeneration.from_pretrained(
            path, local_files_only=True
        )
        tokenizer.src_lang = "zh"
        texts = [segment.text for segment in request.segments]
        encoded = tokenizer(
            texts,
            return_tensors="pt",
            padding=True,
            truncation=True,
            max_length=512,
        )
        generated = model.generate(
            **encoded,
            forced_bos_token_id=tokenizer.get_lang_id("km"),
            max_new_tokens=512,
        )
        translated = tokenizer.batch_decode(generated, skip_special_tokens=True)
        return TranslationBatchResult(
            provider=self.id,
            model=self.selected_model,
            segments=[
                TranslationOutput(id=segment.id, text=text.strip())
                for segment, text in zip(
                    request.segments, translated, strict=True
                )
            ],
        )

    def _translate_causal(
        self, request: TranslationBatchRequest
    ) -> TranslationBatchResult:
        import torch

        tokenizer, model = _load_causal_model(self.selected_model, self.manager)
        outputs: list[TranslationOutput] = []
        for segment in request.segments:
            prompt = _contextual_prompt(segment, request)
            encoded = tokenizer(
                prompt,
                add_special_tokens=False,
                return_tensors="pt",
                truncation=True,
                max_length=2048,
            )
            with torch.inference_mode():
                generated = model.generate(
                    **encoded,
                    do_sample=False,
                    max_new_tokens=256,
                )
            input_length = encoded["input_ids"].shape[1]
            new_tokens = generated[0][input_length:]
            text = tokenizer.decode(new_tokens, skip_special_tokens=True).strip()
            if not text:
                raise ProviderError(
                    f"{self.selected_model} returned an empty translation for {segment.id}."
                )
            outputs.append(TranslationOutput(id=segment.id, text=text))
        return TranslationBatchResult(
            provider=self.id,
            model=self.selected_model,
            segments=outputs,
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
            if spec.runtime == "m2m100":
                return self._translate_m2m100(request)
            if spec.runtime == "causal_translation":
                return self._translate_causal(request)
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
