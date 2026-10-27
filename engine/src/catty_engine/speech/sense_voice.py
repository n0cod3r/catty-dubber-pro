from __future__ import annotations

from pathlib import Path

import sherpa_onnx

from .models import SpeechRegion, TranscriptSegment
from .wav import read_mono_pcm16


class SenseVoiceBackend:
    """Offline multilingual SenseVoice Small backend using sherpa-onnx."""

    id = "sense-small"

    def __init__(
        self,
        model: str | Path,
        tokens: str | Path,
        *,
        model_name: str = "sense-voice-small",
        language: str = "auto",
        use_itn: bool = True,
        num_threads: int = 2,
        provider: str = "cpu",
    ) -> None:
        self._model_path = Path(model).expanduser().resolve()
        self._tokens = Path(tokens).expanduser().resolve()
        if not self._model_path.is_file():
            raise FileNotFoundError(f"SenseVoice model not found: {self._model_path}")
        if not self._tokens.is_file():
            raise FileNotFoundError(f"SenseVoice tokens not found: {self._tokens}")
        self._model_name = model_name
        self._default_language = language
        self._use_itn = use_itn
        self._num_threads = num_threads
        self._provider = provider
        self._recognizers: dict[str, sherpa_onnx.OfflineRecognizer] = {}

    @property
    def model(self) -> str:
        return self._model_name

    def _recognizer(self, language: str) -> sherpa_onnx.OfflineRecognizer:
        selected_language = language or self._default_language
        recognizer = self._recognizers.get(selected_language)
        if recognizer is None:
            recognizer = sherpa_onnx.OfflineRecognizer.from_sense_voice(
                model=str(self._model_path),
                tokens=str(self._tokens),
                num_threads=self._num_threads,
                sample_rate=16_000,
                feature_dim=80,
                decoding_method="greedy_search",
                language=selected_language,
                use_itn=self._use_itn,
                provider=self._provider,
            )
            self._recognizers[selected_language] = recognizer
        return recognizer

    def transcribe(
        self,
        audio: Path,
        regions: list[SpeechRegion],
        *,
        language: str,
    ) -> list[TranscriptSegment]:
        recognizer = self._recognizer(language)
        segments: list[TranscriptSegment] = []
        for region in regions:
            sample_rate, samples = read_mono_pcm16(
                audio,
                start=region.start,
                duration=region.end - region.start,
            )
            if sample_rate != 16_000:
                raise ValueError(
                    f"SenseVoice expects 16 kHz audio, got {sample_rate} Hz"
                )
            if samples.size == 0:
                continue
            stream = recognizer.create_stream()
            stream.accept_waveform(sample_rate, samples)
            recognizer.decode_stream(stream)
            text = stream.result.text.strip()
            if text:
                segments.append(
                    TranscriptSegment(start=region.start, end=region.end, text=text)
                )
        return segments
