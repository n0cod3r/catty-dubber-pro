import json

import pytest

from catty_engine.settings.service import SettingsError, SettingsService


def test_settings_defaults_and_round_trip(tmp_path):
    service = SettingsService(tmp_path)
    defaults = service.get()
    assert defaults.translation.provider == "local"
    assert defaults.translation.target_language == "km"
    assert service.path.exists()

    updated = service.update({"translation": {"provider": "gemini", "providers": {"gemini": {"selected_model": "gemini-test"}}}})
    assert updated.translation.provider == "gemini"
    assert updated.translation.providers.gemini.selected_model == "gemini-test"
    assert SettingsService(tmp_path).get() == updated


def test_invalid_settings_are_not_silently_replaced(tmp_path):
    path = tmp_path / "settings.json"
    path.write_text("{not json", encoding="utf-8")
    with pytest.raises(SettingsError):
        SettingsService(tmp_path).get()
    assert path.read_text(encoding="utf-8") == "{not json"


def test_settings_reject_unknown_fields(tmp_path):
    service = SettingsService(tmp_path)
    service.get()
    with pytest.raises(SettingsError):
        service.update({"unexpected": True})


def test_settings_file_never_contains_credentials(tmp_path):
    service = SettingsService(tmp_path)
    service.get()
    payload = json.loads(service.path.read_text(encoding="utf-8"))
    assert "api_key" not in json.dumps(payload).lower()
