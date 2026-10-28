"""Local and configuration-ready translation providers."""
from __future__ import annotations

from catty_engine.models import LOCAL_TRANSLATION_MODEL, ModelManager

from ..base import ProviderError
from ..models import ConnectionTestResult, TranslationBatchRequest, TranslationBatchResult, TranslationModel, TranslationOutput


class LocalProvider:
    """Offline Chinese → Khmer translation backed by an installed M2M100 model."""

    id = "local"

    def __init__(self, selected_model: str | None = None) -> None:
        self.selected_model = selected_model or LOCAL_TRANSLATION_MODEL.id
        self.manager = ModelManager()

    def list_models(self) -> list[TranslationModel]:
        spec = LOCAL_TRANSLATION_MODEL
        return [TranslationModel(id=spec.id, name=spec.name, description=spec.description)]

    def test_connection(self) -> ConnectionTestResult:
        installed = self.manager.installed(self.selected_model)
        return ConnectionTestResult(
            ok=installed,
            message="Local translation model is ready." if installed else "Local translation model must be downloaded first.",
        )

    def translate_batch(self, request: TranslationBatchRequest) -> TranslationBatchResult:
        if not self.manager.installed(self.selected_model):
            raise ProviderError("Local translation model is not installed. Open Settings → Models to download it.")
        try:
            from transformers import M2M100ForConditionalGeneration, M2M100Tokenizer

            path = self.manager.path_for(self.selected_model)
            tokenizer = M2M100Tokenizer.from_pretrained(path, local_files_only=True)
            model = M2M100ForConditionalGeneration.from_pretrained(path, local_files_only=True)
            tokenizer.src_lang = "zh"
            texts = [segment.text for segment in request.segments]
            encoded = tokenizer(texts, return_tensors="pt", padding=True, truncation=True, max_length=512)
            generated = model.generate(
                **encoded,
                forced_bos_token_id=tokenizer.get_lang_id("km"),
                max_new_tokens=512,
            )
            translated = tokenizer.batch_decode(generated, skip_special_tokens=True)
        except Exception as exc:
            raise ProviderError(f"Local translation failed: {exc}") from exc
        return TranslationBatchResult(
            model=self.selected_model,
            segments=[TranslationOutput(id=segment.id, text=text.strip()) for segment, text in zip(request.segments, translated, strict=True)],
        )


class ConfigurationOnlyProvider:
    """Metadata/config foundation for providers implemented in a later milestone."""

    def __init__(self, provider_id: str, name: str) -> None:
        self.id = provider_id
        self.name = name

    def list_models(self) -> list[TranslationModel]:
        raise ProviderError(f"{self.name} model discovery is not available yet.")

    def test_connection(self) -> ConnectionTestResult:
        return ConnectionTestResult(ok=False, message=f"{self.name} connection testing is not available yet.")

    def translate_batch(self, request: TranslationBatchRequest) -> TranslationBatchResult:
        del request
        raise ProviderError(f"{self.name} translation is not available yet.")
