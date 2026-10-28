"""Structured diagnostics on stderr; stdout remains exclusively JSON IPC."""
from __future__ import annotations

import contextvars
import functools
import json
import logging
import re
import sys
import time
from collections.abc import Callable
from typing import Any, TypeVar

request_id: contextvars.ContextVar[str] = contextvars.ContextVar("request_id", default="-")
F = TypeVar("F", bound=Callable[..., Any])


def redact(message: str) -> str:
    message = re.sub(r"(?i)(bearer\s+)[^\s\"']+", r"\1[REDACTED]", message)
    return re.sub(r"(?i)((?:api[_-]?key|access[_-]?token|authorization|password|secret)[\"']?\s*[:=]\s*[\"']?)[^\s,\"'}]+", r"\1[REDACTED]", message)


class JsonHandler(logging.Handler):
    def emit(self, record: logging.LogRecord) -> None:
        try:
            message = record.getMessage()
            if record.exc_info:
                message += "\n" + logging.Formatter().formatException(record.exc_info)
            sys.stderr.write(json.dumps({"catty_log": True, "logger": record.name, "level": record.levelname,
                "request_id": request_id.get(), "message": redact(message)[:8192]}, ensure_ascii=False) + "\n")
            sys.stderr.flush()
        except Exception:
            self.handleError(record)


def configure_logging() -> None:
    logger = logging.getLogger("catty_engine")
    if not any(isinstance(handler, JsonHandler) for handler in logger.handlers):
        logger.addHandler(JsonHandler())
    logger.setLevel(logging.INFO)
    logger.propagate = False


def logged_process(function: F) -> F:
    """Log stage boundaries and failures without arguments, credentials or text."""
    @functools.wraps(function)
    def run(*args: Any, **kwargs: Any) -> Any:
        logger = logging.getLogger(function.__module__)
        name = function.__qualname__
        started = time.monotonic()
        logger.info("%s started", name)
        try:
            result = function(*args, **kwargs)
        except Exception:
            logger.exception("%s failed after %.2fs", name, time.monotonic() - started)
            raise
        logger.info("%s completed in %.2fs", name, time.monotonic() - started)
        return result
    return run  # type: ignore[return-value]


def logged_request(function: F) -> F:
    @functools.wraps(function)
    def run(payload: Any) -> Any:
        configure_logging()
        token = request_id.set(str(payload.get("id", "-"))[:128] if isinstance(payload, dict) else "-")
        logger = logging.getLogger("catty_engine.ipc")
        method = payload.get("method", "invalid") if isinstance(payload, dict) else "invalid"
        started = time.monotonic()
        logger.info("Request %s started", method)
        try:
            result = function(payload)
            error = result.get("error")
            if error:
                logger.error("Request %s failed (%s): %s", method, error.get("code"), error.get("message"))
            else:
                logger.info("Request %s completed in %.2fs", method, time.monotonic() - started)
            return result
        finally:
            request_id.reset(token)
    return run  # type: ignore[return-value]
