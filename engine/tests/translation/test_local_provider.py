import json

from catty_engine.models import LOCAL_TRANSLATION_MODEL, ModelManager
from catty_engine.translation.models import (
    GlossaryTerm,
    TranslationBatchRequest,
    TranslationContextLine,
    TranslationInput,
)
from catty_engine.translation.providers.other import (
    LocalProvider,
    _MLX_TOKENIZER_CONFIG,
    _hy_mt2_prompt,
    _normalize_mlx_tokenizer_config,
)


def test_preferred_local_model_is_hy_mt2_7b_q4() -> None:
    assert LOCAL_TRANSLATION_MODEL.id == "hy-mt2-7b-q4"
    spec = ModelManager().spec(LOCAL_TRANSLATION_MODEL.id)
    assert spec.runtime == "hy_mt2_mlx"
    assert spec.repository == "mlx-community/Hy-MT2-7B-4bit"


def test_local_models_only_include_hy_mt2_choices() -> None:
    models = {model.id for model in LocalProvider().list_models()}
    assert models == {"hy-mt2-7b-q4", "hy-mt2-1.8b"}


def test_removed_model_selection_migrates_to_recommended_model() -> None:
    provider = LocalProvider(selected_model="m2m100-1.2b")
    assert provider.selected_model == "hy-mt2-7b-q4"


def test_mlx_tokenizer_enables_mistral_regex_compatibility() -> None:
    assert _MLX_TOKENIZER_CONFIG == {"fix_mistral_regex": True}


def test_normalize_mlx_tokenizer_config_repairs_tokenizers_backend(tmp_path) -> None:
    config_path = tmp_path / "tokenizer_config.json"
    config_path.write_text(
        json.dumps({"tokenizer_class": "TokenizersBackend", "model_max_length": 4096}),
        encoding="utf-8",
    )

    assert _normalize_mlx_tokenizer_config(tmp_path) is True
    repaired = json.loads(config_path.read_text(encoding="utf-8"))
    assert repaired["tokenizer_class"] == "PreTrainedTokenizerFast"
    assert repaired["model_max_length"] == 4096
    assert _normalize_mlx_tokenizer_config(tmp_path) is False


def test_normalize_mlx_tokenizer_config_leaves_supported_class_unchanged(tmp_path) -> None:
    config_path = tmp_path / "tokenizer_config.json"
    config_path.write_text(
        json.dumps({"tokenizer_class": "PreTrainedTokenizerFast"}), encoding="utf-8"
    )

    assert _normalize_mlx_tokenizer_config(tmp_path) is False
    assert json.loads(config_path.read_text(encoding="utf-8"))["tokenizer_class"] == "PreTrainedTokenizerFast"


def test_hy_mt2_prompt_translates_only_current_line() -> None:
    request = TranslationBatchRequest(
        glossary=[GlossaryTerm(source="未婚妻", target="គូដណ្តឹង")],
        segments=[
            TranslationInput(
                id="current",
                text="未婚妻啊啊",
                speaker="Speaker 2",
                previous=[
                    TranslationContextLine(
                        id="previous", text="那她是谁？", speaker="Speaker 1"
                    )
                ],
                next=[
                    TranslationContextLine(
                        id="next",
                        text="什么？你什么时候订婚的？",
                        speaker="Speaker 1",
                    )
                ],
            )
        ],
    )

    prompt = _hy_mt2_prompt(request.segments[0], request)

    assert "Previous: Speaker 1: 那她是谁？" in prompt
    assert "Next: Speaker 1: 什么？你什么时候订婚的？" in prompt
    assert "未婚妻 translates to គូដណ្តឹង" in prompt
    assert "Translate ONLY the following Current text into Khmer" in prompt
    assert prompt.endswith("Current: 未婚妻啊啊")
