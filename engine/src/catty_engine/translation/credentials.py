"""Provider-agnostic credential selection and health tracking."""

from __future__ import annotations

import time
from dataclasses import dataclass

from catty_engine.settings.credentials import CredentialStore


@dataclass(frozen=True)
class ProviderCredential:
    id: str
    secret: str


class CredentialPool:
    """Selects usable credentials without exposing provider-specific logic."""

    def __init__(self, provider: str, store: CredentialStore, credential_ids: list[str]) -> None:
        self.provider = provider
        self.store = store
        self.credential_ids = credential_ids
        self._cooldowns: dict[str, float] = {}
        self._invalid: set[str] = set()

    def available(self) -> list[ProviderCredential]:
        now = time.monotonic()
        result: list[ProviderCredential] = []
        for credential_id in self.credential_ids:
            if credential_id in self._invalid or self._cooldowns.get(credential_id, 0) > now:
                continue
            secret = self.store.get(self.provider, credential_id)
            if secret:
                result.append(ProviderCredential(credential_id, secret))
        return result

    def cooldown(self, credential_id: str, seconds: float) -> None:
        self._cooldowns[credential_id] = time.monotonic() + max(1.0, seconds)

    def mark_invalid(self, credential_id: str) -> None:
        self._invalid.add(credential_id)
