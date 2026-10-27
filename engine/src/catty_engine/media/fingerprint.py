from __future__ import annotations

import hashlib
from pathlib import Path

from .errors import MediaError


def source_fingerprint(source: str | Path) -> str:
    path = Path(source).expanduser().resolve()

    if not path.exists():
        raise MediaError(f"Media source does not exist: {path}")

    if not path.is_file():
        raise MediaError(f"Media source is not a file: {path}")

    stat = path.stat()

    value = f"{path}\0{stat.st_size}\0{stat.st_mtime_ns}"

    return hashlib.sha256(value.encode("utf-8")).hexdigest()
