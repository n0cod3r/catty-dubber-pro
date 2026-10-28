"""Out-of-band UI progress on stderr; stdout remains the RPC response channel."""
from __future__ import annotations

import json
import sys
from typing import Any


def emit_translation_progress(payload: dict[str, Any]) -> None:
    sys.stderr.write(json.dumps({"catty_progress": "translation", "payload": payload}, ensure_ascii=False) + "\n")
    sys.stderr.flush()
