"""Platform application-data paths for Catty settings and credentials."""

from __future__ import annotations

import os
import sys
from pathlib import Path

APP_DIR_NAME = "Catty Dubber Pro"


def app_data_dir() -> Path:
    """Return the writable application-data root (never the project folder)."""
    override = os.environ.get("CATTY_APP_DATA")
    if override:
        return Path(override).expanduser().resolve()
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / APP_DIR_NAME
    if os.name == "nt":
        base = Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming"))
        return base / APP_DIR_NAME
    base = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
    return base / "catty-dubber-pro"


def settings_file() -> Path:
    return app_data_dir() / "settings.json"


def credentials_file() -> Path:
    """Fallback secret file used only when the OS keychain is unavailable."""
    return app_data_dir() / "credentials.json"
