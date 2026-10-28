"""Local and configuration-ready translation providers."""
from __future__ import annotations

import importlib
import importlib.util
import json
import platform
from pathlib import Path
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

_TRANSFORMERS_MODEL_CACHE: dict[str, tuple[Any, Any, str]] = {}
_MLX_MODEL_CACHE: dict[str, tuple[Any, Any]] = {}
_MLX_TOKENIZER_CONFIG: dict[str, Any] = {"fix_mistral_regex": True}


def _hy_mt2_prompt(segment: TranslationInput, request: TranslationBatchRequest) -> str:
    """Build an Hy-MT2 instruction while keeping surrounding dialogue read-only."""
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
    lines.extend([
        "Translate ONLY the following Current text into Khmer. Only output the translated result without any additional explanation:",
        f"Current: {segment.text}",
    ])
    return "\n".join(lines)


_contextual_prompt = _hy_mt2_prompt


def _chat_prompt(tokenizer: Any, prompt: str) -> str:
    """Render HY-MT2 input with the model's native chat template."""
    rendered = tokenizer.apply_chat_template(
        [{"role": "user", "content": prompt}],
        tokenize=False,
        add_generation_prompt=True,
    )
    if not isinstance(rendered, str):
        raise ProviderError("HY-MT2 tokenizer returned an invalid chat prompt.")
    return rendered


def _torch_device() -> str:
    import torch
    if torch.cuda.is_available():
        return "cuda"
    if torch.backends.mps.is_available():
        return "mps"
    return "cpu"


def _load_transformers_model(model_id: str, manager: ModelManager) -> tuple[Any, Any, str]:
    cached = _TRANSFORMERS_MODEL_CACHE.get(model_id)
    if cached is not None:
        return cached
    from transformers import AutoModelForCausalLM, AutoTokenizer
    path = manager.path_for(model_id)
    device = _torch_device()
    tokenizer = AutoTokenizer.from_pretrained(path, local_files_only=True)
    # Transformers' generic return type is not compatible with its own `.to`
    # overloads across supported releases; the runtime object is a standard
    # PreTrainedModel.
    model: Any = AutoModelForCausalLM.from_pretrained(path, local_files_only=True)
    model.to(device)
    model.eval()
    result = (tokenizer, model, device)
    _TRANSFORMERS_MODEL_CACHE[model_id] = result
    return result


def _mlx_runtime() -> Any:
    if importlib.util.find_spec("mlx_lm") is None:
        raise ProviderError("Hy-MT2 7B 4-bit requires the Catty MLX runtime (mlx-lm).")
    return importlib.import_module("mlx_lm")


def _normalize_mlx_tokenizer_config(model_path: Path) -> bool:
    """Repair tokenizer metadata emitted by some MLX community conversions."""
    config_path = model_path / "tokenizer_config.json"
    if not config_path.is_file():
        return False
    try:
        config = json.loads(config_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ProviderError(f"Could not read local tokenizer configuration: {exc}") from exc
    if config.get("tokenizer_class") != "TokenizersBackend":
        return False
    config["tokenizer_class"] = "PreTrainedTokenizerFast"
    try:
        config_path.write_text(
            json.dumps(config, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    except OSError as exc:
        raise ProviderError(f"Could not repair local tokenizer configuration: {exc}") from exc
    return True


def _load_mlx_model(model_id: str, manager: ModelManager) -> tuple[Any, Any]:
    cached = _MLX_MODEL_CACHE.get(model_id)
    if cached is not None:
        return cached
    if platform.system() != "Darwin" or platform.machine() not in {"arm64", "aarch64"}:
        raise ProviderError("Hy-MT2 7B 4-bit requires an Apple Silicon Mac.")
    mlx_lm = _mlx_runtime()
    model_path = manager.path_for(model_id)
    _normalize_mlx_tokenizer_config(model_path)
    load: Any = getattr(mlx_lm, "load")
    model, tokenizer = load(
        str(model_path),
        tokenizer_config=dict(_MLX_TOKENIZER_CONFIG),
    )
    result = (model, tokenizer)
    _MLX_MODEL_CACHE[model_id] = result
    return result


class LocalProvider:
    """Offline Chinese → Khmer translation using a user-selected Hy-MT2 model."""

    id = "local"

    def __init__(self, selected_model: str | None = None) -> None:
        candidate = selected_model or LOCAL_TRANSLATION_MODEL.id
        self.manager = ModelManager()
        try:
            self.manager.spec(candidate)
        except ValueError:
            candidate = LOCAL_TRANSLATION_MODEL.id
        self.selected_model = candidate

    def list_models(self) -> list[TranslationModel]:
        return [TranslationModel(id=spec.id, name=spec.name, description=spec.description) for spec in self.manager.list_specs(kind="translation")]

    def test_connection(self) -> ConnectionTestResult:
        spec = self.manager.spec(self.selected_model)
        if not self.manager.installed(self.selected_model):
            return ConnectionTestResult(ok=False, message=f"{spec.name} must be downloaded first.")
        if spec.runtime == "hy_mt2_mlx":
            if platform.system() != "Darwin" or platform.machine() not in {"arm64", "aarch64"}:
                return ConnectionTestResult(ok=False, message=f"{spec.name} requires an Apple Silicon Mac.")
            if importlib.util.find_spec("mlx_lm") is None:
                return ConnectionTestResult(ok=False, message=f"{spec.name} requires the Catty MLX runtime (mlx-lm).")
            try:
                _normalize_mlx_tokenizer_config(self.manager.path_for(self.selected_model))
            except ProviderError as exc:
                return ConnectionTestResult(ok=False, message=str(exc))
        return ConnectionTestResult(ok=True, message=f"{spec.name} is ready for offline translation.")

    def _translate_transformers(self, request: TranslationBatchRequest) -> TranslationBatchResult:
        import torch
        tokenizer, model, device = _load_transformers_model(self.selected_model, self.manager)
        outputs: list[TranslationOutput] = []
        for segment in request.segments:
            prompt = _chat_prompt(tokenizer, _hy_mt2_prompt(segment, request))
            encoded = tokenizer(
                prompt,
                add_special_tokens=False,
                return_tensors="pt",
                truncation=True,
                max_length=2048,
            )
            # HY-MT2's tokenizer can emit token_type_ids, but its causal LM does
            # not accept them during generation.
            encoded.pop("token_type_ids", None)
            encoded = {key: value.to(device) for key, value in encoded.items()}
            with torch.inference_mode():
                generated = model.generate(
                    **encoded,
                    do_sample=False,
                    max_new_tokens=256,
                    repetition_penalty=1.05,
                )
            input_length = encoded["input_ids"].shape[1]
            text = tokenizer.decode(generated[0][input_length:], skip_special_tokens=True).strip()
            if not text:
                raise ProviderError(f"{self.selected_model} returned an empty translation for {segment.id}.")
            outputs.append(TranslationOutput(id=segment.id, text=text))
        return TranslationBatchResult(provider=self.id, model=self.selected_model, segments=outputs)

    def _translate_mlx(self, request: TranslationBatchRequest) -> TranslationBatchResult:
        mlx_lm: Any = _mlx_runtime()
        model, tokenizer = _load_mlx_model(self.selected_model, self.manager)
        generate: Any = getattr(mlx_lm, "generate")
        outputs: list[TranslationOutput] = []
        for segment in request.segments:
            prompt = _chat_prompt(tokenizer, _hy_mt2_prompt(segment, request))
            text = generate(
                model,
                tokenizer,
                prompt=prompt,
                max_tokens=256,
                verbose=False,
            ).strip()
            if not text:
                raise ProviderError(f"{self.selected_model} returned an empty translation for {segment.id}.")
            outputs.append(TranslationOutput(id=segment.id, text=text))
        return TranslationBatchResult(provider=self.id, model=self.selected_model, segments=outputs)

    def translate_batch(self, request: TranslationBatchRequest) -> TranslationBatchResult:
        if request.source_language != "zh" or request.target_language != "km":
            raise ProviderError("Catty local translation currently supports Chinese → Khmer only.")
        if not self.manager.installed(self.selected_model):
            raise ProviderError("Selected local translation model is not installed. Open Settings → Models to download it.")
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
        return ConnectionTestResult(ok=False, message=f"{self.name} connection testing is not available yet.")

    def translate_batch(self, request: TranslationBatchRequest) -> TranslationBatchResult:
        del request
        raise ProviderError(f"{self.name} translation is not available yet.")
