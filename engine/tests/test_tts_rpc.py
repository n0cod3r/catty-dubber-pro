from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pytest
from pydantic import ValidationError

from catty_engine.tts.rpc import (
    TTSAssignSegmentVoiceParams,
    TTSGenerateParams,
    TTSPreviewParams,
)


def test_tts_generate_params_reject_invalid_controls(tmp_path: Path) -> None:
    with pytest.raises(ValidationError):
        TTSGenerateParams(
            project_directory=tmp_path,
            episode_id=uuid4(),
            voice_profile_id=uuid4(),
            speed=2.1,
        )


def test_tts_selected_generation_accepts_segment_ids(tmp_path: Path) -> None:
    segment_id = uuid4()
    params = TTSGenerateParams(
        operation_id="tts-job",
        project_directory=tmp_path,
        episode_id=uuid4(),
        voice_profile_id=uuid4(),
        mode="selected",
        segment_ids=[segment_id],
        speed=1.1,
        pitch=4,
        volume=-2,
    )
    assert params.segment_ids == [segment_id]
    assert params.operation_id == "tts-job"


def test_tts_preview_requires_text(tmp_path: Path) -> None:
    with pytest.raises(ValidationError):
        TTSPreviewParams(project_directory=tmp_path, text="", voice_id="km-KH-SreymomNeural")


def test_tts_assign_segment_voice_allows_clearing_override(tmp_path: Path) -> None:
    params = TTSAssignSegmentVoiceParams(
        project_directory=tmp_path,
        episode_id=uuid4(),
        segment_id=uuid4(),
    )
    assert params.voice_profile_id is None
    with pytest.raises(ValidationError):
        TTSAssignSegmentVoiceParams(
            project_directory=tmp_path,
            episode_id=uuid4(),
            segment_id=uuid4(),
            voice_profile_id="",
        )
