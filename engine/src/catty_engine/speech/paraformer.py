from __future__ import annotations

from pathlib import Path

import sherpa_onnx

from .models import SpeechRegion, TranscriptSegment
from .wav import read_mono_pcm16


class ParaformerBackend:
    """Offline Chinese/English Paraformer backend using sherpa-onnx."""

    id = "paraformer"

    def __init__(
        self,
        model: str | Path,
        tokens: str | Path,
        *,
        model_name: str = "paraformer-zh",
        num_threads: int = 2,
        provider: str = "cpu",
    ) -> None:
        self._model_path = Path(model).expanduser().resolve()
        self._tokens = Path(tokens).expanduser().resolve()
        if not self._model_path.is_file():
            raise FileNotFoundError(f"Paraformer model not found: {self._model_path}")
        if not self._tokens.is_file():
            raise FileNotFoundError(f"Paraformer tokens not found: {self._tokens}")
        self._model_name = model_name
        self._recognizer = sherpa_onnx.OfflineRecognizer.from_paraformer(
            paraformer=str(self._model_path),
            tokens=str(self._tokens),
            num_threads=num_threads,
            sample_rate=16_000,
            feature_dim=80,
            provider=provider,
        )

    @property
    def model(self) -> str:
        return self._model_name

    def transcribe(
        self,
        audio: Path,
        regions: list[SpeechRegion],
        *,
        language: str,
    ) -> list[TranscriptSegment]:
        # Paraformer model choice determines supported languages. Keep language in
        # the shared backend contract so multilingual/future backends can use it.
        del language
        segments: list[TranscriptSegment] = []
        for region in regions:
            duration = region.end - region.start
            sample_rate, samples = read_mono_pcm16(
                audio,
                start=region.start,
                duration=duration,
            )
            if sample_rate != 16_000:
                raise ValueError(f"Paraformer expects 16 kHz audio, got {sample_rate} Hz")
            if samples.size == 0:
                continue
            stream = self._recognizer.create_stream()
            stream.accept_waveform(sample_rate, samples)
            self._recognizer.decode_stream(stream)
            text = stream.result.text.strip()
            if not text:
                continue
            segments.append(
                TranscriptSegment(
                    start=region.start,
                    end=region.end,
                    text=text,
                )
            )
        return segments
