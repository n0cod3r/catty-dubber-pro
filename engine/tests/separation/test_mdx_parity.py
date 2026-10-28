"""Numeric check against stems produced by the UVR reference implementation.

Set the CATTY_MDX_* variables to the audio-separator run artifacts to enable:
    CATTY_MDX_MODEL=/path/UVR-MDX-NET-Inst_HQ_3.onnx
    CATTY_MDX_SOURCE=/path/input.wav
    CATTY_MDX_STEM=/path/input_(Instrumental)_UVR-MDX-NET-Inst_HQ_3.wav
"""
from __future__ import annotations

import os
from pathlib import Path

import numpy as np
import pytest
import soundfile

from catty_engine.separation import MdxBackgroundExtractor

MODEL = os.environ.get("CATTY_MDX_MODEL")
SOURCE = os.environ.get("CATTY_MDX_SOURCE")
STEM = os.environ.get("CATTY_MDX_STEM")

pytestmark = pytest.mark.skipif(
    not all(value and Path(value).is_file() for value in (MODEL, SOURCE, STEM)),
    reason="Set CATTY_MDX_MODEL, CATTY_MDX_SOURCE and CATTY_MDX_STEM to compare stems",
)


def test_background_matches_reference_stem(tmp_path: Path) -> None:
    assert MODEL and SOURCE and STEM
    reference, reference_rate = soundfile.read(STEM, dtype="float32", always_2d=True)
    destination = tmp_path / "background.wav"

    MdxBackgroundExtractor(MODEL).extract_background(Path(SOURCE), destination)

    produced, rate = soundfile.read(destination, dtype="float32", always_2d=True)
    assert rate == reference_rate == 44_100
    assert produced.shape == reference.shape

    difference = np.abs(produced - reference)
    assert float(difference.max()) < 5e-3
    assert float(difference.mean()) < 1e-4
