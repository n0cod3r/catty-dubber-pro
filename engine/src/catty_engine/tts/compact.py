"""Local-only handoff to the desktop WebGPU worker; Python owns the output file."""
from __future__ import annotations

import io
import json
import logging
import secrets
import tempfile
import threading
import wave
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

from catty_engine.media.ffmpeg import FFmpegRunner
from catty_engine.models import ModelManager
from catty_engine.progress import _emit

logger = logging.getLogger(__name__)
MAX_AUDIO_BYTES = 48_000 * 2 * 30 + 4096
ALLOWED_ORIGINS = {"tauri://localhost", "http://tauri.localhost", "https://tauri.localhost", "http://localhost:1420", "http://127.0.0.1:1420", "http://localhost:1422"}


def text_tokens(path: Path, text: str) -> list[int]:
    from tokenizers import Tokenizer  # type: ignore[import-untyped]
    tokenizer = Tokenizer.from_file(str(path))
    encoded = tokenizer.encode(text, add_special_tokens=False)
    result: list[int] = []
    for token, token_id in zip(encoded.tokens, encoded.ids, strict=True):
        clean = token.replace("▁", "")
        if len(clean) > 1 and all("\u4e00" <= char <= "\u9fff" for char in clean):
            result.extend(tokenizer.token_to_id(char) or 0 for char in clean)
        else:
            result.append(token_id)
    return result + [101]


def validate_wave(data: bytes) -> None:
    with wave.open(io.BytesIO(data), "rb") as audio:
        if audio.getnchannels() != 1 or audio.getsampwidth() != 2 or audio.getframerate() != 48000:
            raise ValueError("Compact speech must be 48 kHz mono PCM16 WAV")
        if not 0 < audio.getnframes() <= 48_000 * 30:
            raise ValueError("Compact speech must contain at most 30 seconds of audio")
        if len(audio.readframes(audio.getnframes())) != audio.getnframes() * 2:
            raise ValueError("Compact speech WAV is incomplete")


class CompactVoxCPM2Provider:
    def synthesize(self, text: str, output: Path, *, reference: Path | None = None,
                   reference_text: str | None = None, style: str = "") -> Path:
        manager = ModelManager()
        if not manager.installed("voxcpm2-compact"):
            raise ValueError("Download VoxCPM2 Compact in Settings → Models")
        root = manager.path_for("voxcpm2-compact")
        manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
        allowed = {"manifest.json", "tokenizer.json", "tokenizer_config.json", "special_tokens_map.json"}
        for item in manifest["files"]:
            allowed.add(item["path"])
            allowed.update(data["path"] for data in item.get("externalData", []))
        token = secrets.token_urlsafe(32)
        done = threading.Event()
        accepted = threading.Event()
        outcome: dict[str, Any] = {}
        with tempfile.TemporaryDirectory(prefix="catty-compact-") as temporary:
            ref = Path(temporary) / "reference.wav"
            if reference:
                FFmpegRunner().extract_speech_audio(reference, ref)

            class Handler(BaseHTTPRequestHandler):
                def log_message(self, *_args: Any) -> None:
                    pass

                def _headers(self, status: int, length: int = 0, content_type: str = "application/octet-stream") -> None:
                    self.send_response(status)
                    origin = self.headers.get("Origin", "")
                    if origin in ALLOWED_ORIGINS:
                        self.send_header("Access-Control-Allow-Origin", origin)
                    self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
                    self.send_header("Access-Control-Allow-Headers", "Content-Type")
                    self.send_header("Content-Type", content_type)
                    self.send_header("Content-Length", str(length))
                    self.send_header("Cache-Control", "no-store")
                    self.end_headers()

                def _route(self) -> str | None:
                    if self.headers.get("Origin", "") not in ALLOWED_ORIGINS | {""}:
                        return None
                    prefix = f"/{token}/"
                    return self.path[len(prefix):] if self.path.startswith(prefix) else None

                def do_OPTIONS(self) -> None:
                    self._headers(204 if self._route() is not None else 403)

                def do_GET(self) -> None:
                    route = self._route()
                    if route == "reference.wav" and reference:
                        path = ref
                    elif route in allowed:
                        path = (root / str(route)).resolve()
                        if not path.is_relative_to(root.resolve()):
                            self._headers(403)
                            return
                    else:
                        self._headers(404)
                        return
                    if not path.is_file():
                        self._headers(404)
                        return
                    self._headers(200, path.stat().st_size)
                    try:
                        with path.open("rb") as stream:
                            while chunk := stream.read(1024 * 1024):
                                self.wfile.write(chunk)
                    except (BrokenPipeError, ConnectionResetError):
                        pass

                def do_POST(self) -> None:
                    route = self._route()
                    try:
                        length = int(self.headers.get("Content-Length", "0"))
                        if route == "accepted":
                            accepted.set()
                            self._headers(200)
                            return
                        if route not in {"result", "error"} or not 0 < length <= MAX_AUDIO_BYTES or done.is_set():
                            self._headers(400)
                            return
                        data = self.rfile.read(length)
                        if route == "error":
                            outcome["error"] = data[:8192].decode("utf-8", errors="replace")
                        else:
                            validate_wave(data)
                            outcome["audio"] = data
                        self._headers(200)
                        done.set()
                    except (ValueError, wave.Error) as exc:
                        outcome["error"] = str(exc)
                        self._headers(400)
                        done.set()

            server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
            server.daemon_threads = True
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            url = f"http://127.0.0.1:{server.server_port}/{token}/"
            try:
                logger.info("Requesting compact VoxCPM2 inference from the desktop worker")
                _emit("compact-inference", {"operation_id": token, "episode_id": "voice-runtime", "phase": "generate",
                    "url": url, "model_version": manifest["version"], "text": text, "style": style,
                    "has_reference": reference is not None, "reference_text": reference_text,
                    "tokens": text_tokens(root / "tokenizer.json", (reference_text or "") + (f"({style.strip()})" if style.strip() else "") + text.strip())})
                if not accepted.wait(15):
                    raise RuntimeError("Compact runtime is not connected. Restart the Catty desktop app before using this model.")
                if not done.wait(600):
                    raise RuntimeError("Compact worker did not return audio. Restart Catty and check WebGPU support, or select original VoxCPM2 in Settings → Models.")
                if "error" in outcome:
                    raise RuntimeError(f"Compact VoxCPM2: {outcome['error']}")
                output.parent.mkdir(parents=True, exist_ok=True)
                output.write_bytes(outcome["audio"])
                return output
            finally:
                server.shutdown()
                server.server_close()
