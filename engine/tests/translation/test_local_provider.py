from catty_engine.models import LOCAL_TRANSLATION_MODEL, ModelManager
from catty_engine.translation.models import (
    GlossaryTerm,
    TranslationBatchRequest,
    TranslationContextLine,
    TranslationInput,
)
from catty_engine.translation.providers.other import LocalProvider, _contextual_prompt


def test_preferred_local_model_is_contextual_milmmt() -> None:
    assert LOCAL_TRANSLATION_MODEL.id == "milmmt-46-1b-v1"
    spec = ModelManager().spec(LOCAL_TRANSLATION_MODEL.id)
    assert spec.runtime == "causal_translation"
    assert spec.repository == "xiaomi-research/MiLMMT-46-1B-v1.0"


def test_local_models_include_contextual_candidates_and_legacy_m2m100() -> None:
    models = {model.id for model in LocalProvider().list_models()}
    assert "milmmt-46-1b-v1" in models
    assert "gemmax2-28-2b-v0.2" in models
    assert "m2m100-418m" in models


def test_contextual_prompt_translates_only_current_line() -> None:
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

    prompt = _contextual_prompt(request.segments[0], request)

    assert "Previous: Speaker 1: 那她是谁？" in prompt
    assert "Next: Speaker 1: 什么？你什么时候订婚的？" in prompt
    assert "Translate only the Current line below." in prompt
    assert "未婚妻 -> គូដណ្តឹង" in prompt
    assert "Chinese (Simplified): 未婚妻啊啊" in prompt
    assert prompt.endswith("Khmer:")
