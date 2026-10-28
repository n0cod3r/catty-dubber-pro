from __future__ import annotations

import asyncio
from pathlib import Path
from typing import TypedDict, cast


class EdgeVoice(TypedDict, total=False):
    ShortName: str
    FriendlyName: str
    Locale: str
    Gender: str


class EdgeTTSError(RuntimeError):
    """Raised when Edge TTS cannot synthesize an utterance."""


class EdgeTTSProvider:
    """Small adapter around edge-tts so the rest of Catty is provider agnostic."""

    async def _synthesize(
        self,
        text: str,
        output: Path,
        *,
        voice: str,
        speed: float,
        pitch: int,
        volume: int,
    ) -> None:
        import edge_tts

        communicate = edge_tts.Communicate(
            text,
            voice,
            rate=self._rate(speed),
            pitch=f"{pitch:+d}Hz",
            volume=f"{volume:+d}%",
        )
        await communicate.save(str(output))

    async def _voices(self) -> list[EdgeVoice]:
        import edge_tts

        voices = cast(list[EdgeVoice], await edge_tts.list_voices())
        return [
            voice
            for voice in voices
            if str(voice.get("Locale", "")).lower() == "km-kh"
        ]

    def list_voices(self) -> list[dict[str, str]]:
        try:
            voices = asyncio.run(self._voices())
        except Exception as exc:
            raise EdgeTTSError(f"Could not load Edge TTS voices: {exc}") from exc
        return [
            {
                "id": str(voice.get("ShortName", "")),
                "name": str(voice.get("FriendlyName") or voice.get("ShortName", "")),
                "locale": str(voice.get("Locale", "km-KH")),
                "gender": str(voice.get("Gender", "")),
            }
            for voice in voices
            if voice.get("ShortName")
        ]

    def synthesize(
        self,
        text: str,
        output: Path,
        *,
        voice: str,
        speed: float = 1.0,
        pitch: int = 0,
        volume: int = 0,
    ) -> Path:
        if not text.strip():
            raise ValueError("TTS text cannot be empty")
        if not voice.strip():
            raise ValueError("Edge TTS voice cannot be empty")
        if not 0.5 <= speed <= 2.0:
            raise ValueError("TTS speed must be between 0.5 and 2.0")
        if not -100 <= pitch <= 100:
            raise ValueError("TTS pitch must be between -100 and 100 Hz")
        if not -100 <= volume <= 100:
            raise ValueError("TTS volume must be between -100 and 100 percent")

        output.parent.mkdir(parents=True, exist_ok=True)
        temporary = output.with_suffix(output.suffix + ".part")
        temporary.unlink(missing_ok=True)
        try:
            asyncio.run(
                self._synthesize(
                    text.strip(),
                    temporary,
                    voice=voice,
                    speed=speed,
                    pitch=pitch,
                    volume=volume,
                )
            )
            if not temporary.is_file() or temporary.stat().st_size == 0:
                raise EdgeTTSError("Edge TTS returned no audio")
            temporary.replace(output)
        except Exception as exc:
            temporary.unlink(missing_ok=True)
            if isinstance(exc, (ValueError, EdgeTTSError)):
                raise
            raise EdgeTTSError(f"Edge TTS synthesis failed: {exc}") from exc
        return output

    @staticmethod
    def _rate(speed: float) -> str:
        percent = round((speed - 1.0) * 100)
        return f"{percent:+d}%"
