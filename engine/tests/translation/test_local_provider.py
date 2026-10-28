from catty_engine.models import LOCAL_TRANSLATION_MODEL, ModelManager
from catty_engine.translation.models import (
    GlossaryTerm,
    TranslationBatchRequest,
    TranslationContextLine,
    TranslationInput,
)
from catty_engine.translation.providers.other import LocalProvider, _hy_mt2_prompt


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
