"""UVR MDX-Net background separation on ONNX Runtime.

The model input is a normalized 4-channel spectrogram (real/imaginary for both
stereo channels) and it predicts the instrumental stem. Chunking, windowing and
normalization mirror the UVR reference implementation so results stay close to
the stems users already know from UVR/audio-separator.
"""
from __future__ import annotations

import logging
import tempfile
import uuid
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import soundfile
import torch
from torch.nn import functional as torch_functional

from catty_engine.logging import logged_process
from catty_engine.media.ffmpeg import FFmpegRunner

from .errors import SeparationError

logger = logging.getLogger("catty_engine.separation")

SAMPLE_RATE = 44_100
CHANNELS = 2
BACKGROUND_FILE_NAME = "background.wav"


@dataclass(frozen=True)
class MdxModelConfig:
    n_fft: int
    dim_f: int
    dim_t: int
    hop_length: int = 1024
    segment_size: int = 256
    overlap: float = 0.25
    # UVR normalizes the mix and the written stem to this peak.
    peak: float = 0.9


UVR_MDX_INST_HQ_3 = MdxModelConfig(n_fft=6144, dim_f=3072, dim_t=256)


class MdxSeparator:
    """Predicts the instrumental stem for a (2, samples) float32 waveform."""

    def __init__(
        self,
        model_path: str | Path,
        *,
        config: MdxModelConfig = UVR_MDX_INST_HQ_3,
    ) -> None:
        self._model_path = Path(model_path).expanduser().resolve()
        self._config = config
        self._session = None
        self._window = torch.hann_window(config.n_fft, periodic=True, dtype=torch.float32)

    def separate(self, mixture: np.ndarray) -> np.ndarray:
        config = self._config
        if mixture.ndim != 2 or mixture.shape[0] != CHANNELS:
            raise SeparationError("MDX separation expects a 2-channel waveform")
        if mixture.shape[1] == 0:
            raise SeparationError("MDX separation received empty audio")
        if not np.isfinite(mixture).all():
            raise SeparationError("MDX separation received non-finite samples")

        mix = np.ascontiguousarray(mixture, dtype=np.float32)
        peak = float(np.abs(mix).max())
        if peak == 0:
            return np.zeros_like(mix)
        if peak > config.peak:
            mix = mix * (config.peak / peak)

        background = self._demix(mix) * peak
        background = _normalize(background, config.peak)
        return background.astype(np.float32, copy=False)

    def _demix(self, mix: np.ndarray) -> np.ndarray:
        config = self._config
        trim = config.n_fft // 2
        chunk_size = config.hop_length * (config.segment_size - 1)
        gen_size = chunk_size - 2 * trim
        samples = mix.shape[1]

        # Align the mixture so the trimmed output still covers the last sample.
        pad = gen_size + trim - samples % gen_size
        mixture = np.concatenate(
            (
                np.zeros((CHANNELS, trim), dtype=np.float32),
                mix,
                np.zeros((CHANNELS, pad), dtype=np.float32),
            ),
            axis=1,
        )

        step = int((1 - config.overlap) * chunk_size)
        result = np.zeros((1, CHANNELS, mixture.shape[1]), dtype=np.float32)
        divider = np.zeros_like(result)

        for start in range(0, mixture.shape[1], step):
            end = min(start + chunk_size, mixture.shape[1])
            actual = end - start
            part = mixture[:, start:end]
            if actual != chunk_size:
                part = np.concatenate(
                    (part, np.zeros((CHANNELS, chunk_size - actual), dtype=np.float32)),
                    axis=1,
                )

            window = None
            if config.overlap:
                window = np.hanning(actual).astype(np.float32)
                window = np.tile(window[None, None, :], (1, CHANNELS, 1))

            estimate = self._run_chunk(part[None, ...])
            if window is not None:
                estimate[..., :actual] *= window
                divider[..., start:end] += window
            else:
                divider[..., start:end] += 1
            result[..., start:end] += estimate[..., :actual]

        # Both ends of a Hann window are zero; those samples are trimmed below.
        combined = np.divide(result, divider, out=np.zeros_like(result), where=divider != 0)
        combined = combined[..., trim:-trim]
        return combined[0, :, :samples]

    def _run_chunk(self, part: np.ndarray) -> np.ndarray:
        spectrum = self._stft(torch.from_numpy(part))
        if spectrum.shape[-2:] != (self._config.dim_f, self._config.dim_t):
            raise SeparationError(
                "Unexpected MDX spectrogram shape "
                f"{tuple(spectrum.shape)}; expected frequency {self._config.dim_f} "
                f"and {self._config.dim_t} frames"
            )
        # UVR discards the lowest three bins to reduce rumble.
        spectrum[:, :, :3, :] = 0
        prediction = self._onnx_session().run(None, {"input": spectrum.numpy()})[0]
        return self._istft(prediction)

    def _stft(self, waveform: torch.Tensor) -> torch.Tensor:
        # waveform: (batch, 2, samples) -> (batch, 4, dim_f, frames)
        batch = waveform.shape[:-2]
        channels, samples = waveform.shape[-2:]
        transformed = torch.view_as_real(
            torch.stft(
                waveform.reshape(-1, samples),
                n_fft=self._config.n_fft,
                hop_length=self._config.hop_length,
                window=self._window,
                center=True,
                return_complex=True,
            )
        )
        # (channels, frequency, frames, 2) -> (channels * 2, frequency, frames)
        permuted = transformed.permute(0, 3, 1, 2)
        reshaped = permuted.reshape(*batch, channels * 2, -1, permuted.shape[-1])
        return reshaped[..., : self._config.dim_f, :]

    def _istft(self, prediction: np.ndarray) -> np.ndarray:
        # prediction: (batch, 4, dim_f, frames) -> (batch, 2, samples)
        spectrum = torch.from_numpy(np.ascontiguousarray(prediction, dtype=np.float32))
        batch = spectrum.shape[:-3]
        channels, frequency, frames = spectrum.shape[-3:]
        bins = self._config.n_fft // 2 + 1
        if frequency < bins:
            spectrum = torch_functional.pad(spectrum, (0, 0, 0, bins - frequency))
        spectrum = spectrum.reshape(*batch, channels // 2, 2, bins, frames)
        spectrum = spectrum.reshape(-1, 2, bins, frames).permute(0, 2, 3, 1)
        complex_spectrum = torch.complex(spectrum[..., 0], spectrum[..., 1])
        waveform = torch.istft(
            complex_spectrum,
            n_fft=self._config.n_fft,
            hop_length=self._config.hop_length,
            window=self._window,
            center=True,
        )
        return waveform.reshape(*batch, CHANNELS, -1).numpy()

    def _onnx_session(self):
        if self._session is None:
            if not self._model_path.is_file():
                raise SeparationError(f"Separation model is not installed: {self._model_path}")
            import onnxruntime

            options = onnxruntime.SessionOptions()
            options.log_severity_level = 3
            self._session = onnxruntime.InferenceSession(
                str(self._model_path),
                providers=["CPUExecutionProvider"],
                sess_options=options,
            )
        return self._session


def _normalize(waveform: np.ndarray, peak: float) -> np.ndarray:
    maximum = float(np.abs(waveform).max())
    if maximum > peak:
        return waveform * (peak / maximum)
    return waveform


class MdxBackgroundExtractor:
    """Decodes a media source and writes its instrumental stem as a WAV file."""

    def __init__(
        self,
        model_path: str | Path,
        *,
        config: MdxModelConfig = UVR_MDX_INST_HQ_3,
        ffmpeg: FFmpegRunner | None = None,
    ) -> None:
        self._separator = MdxSeparator(model_path, config=config)
        self._ffmpeg = ffmpeg or FFmpegRunner()

    @logged_process
    def extract_background(self, source: Path, destination: Path) -> None:
        source = source.expanduser().resolve()
        destination = destination.expanduser().resolve()
        if source == destination:
            raise SeparationError("Separated audio must not overwrite its source file")
        if not source.is_file():
            raise SeparationError(f"Media source is not a file: {source}")

        destination.parent.mkdir(parents=True, exist_ok=True)
        temporary = destination.with_name(f".{destination.stem}-{uuid.uuid4().hex}.wav")
        try:
            with tempfile.TemporaryDirectory(prefix="catty-separation-") as work:
                decoded = Path(work) / "mix.wav"
                self._ffmpeg.decode_stereo_audio(source, decoded, sample_rate=SAMPLE_RATE)
                mix, rate = soundfile.read(decoded, dtype="float32", always_2d=True)
            if rate != SAMPLE_RATE:
                raise SeparationError(f"Decoded audio uses {rate} Hz instead of {SAMPLE_RATE} Hz")

            background = self._separator.separate(np.ascontiguousarray(mix.T))
            soundfile.write(
                temporary,
                background.T,
                SAMPLE_RATE,
                subtype="PCM_16",
                format="WAV",
            )
            temporary.replace(destination)
        except OSError as exc:
            raise SeparationError(f"Could not write separated audio: {exc}") from exc
        finally:
            temporary.unlink(missing_ok=True)
