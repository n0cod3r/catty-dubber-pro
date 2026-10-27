"""Secure provider credentials stored in the operating-system keychain."""

from __future__ import annotations

SERVICE_NAME = "Catty Dubber Pro"


class CredentialError(RuntimeError):
    """Credential storage is unavailable or failed."""


class CredentialStore:
    """OS-keychain-only credential storage for macOS and Windows.

    Secrets are never written to settings.json/project.json and are never returned
    to the renderer. The renderer only receives credential-configured booleans.
    """

    def get(self, provider: str) -> str | None:
        self._validate(provider)
        keyring = self._keyring()
        try:
            value = keyring.get_password(SERVICE_NAME, provider)
        except Exception as exc:
            raise CredentialError("Secure credential storage is unavailable.") from exc
        return value.strip() if value else None

    def set(self, provider: str, secret: str) -> None:
        self._validate(provider)
        secret = secret.strip()
        if not secret:
            raise ValueError("Credential must not be empty")
        try:
            self._keyring().set_password(SERVICE_NAME, provider, secret)
        except Exception as exc:
            raise CredentialError("Could not save the credential securely.") from exc

    def delete(self, provider: str) -> None:
        self._validate(provider)
        try:
            self._keyring().delete_password(SERVICE_NAME, provider)
        except Exception as exc:
            # Missing credentials are already equivalent to deleted.
            if exc.__class__.__name__ != "PasswordDeleteError":
                raise CredentialError("Could not remove the saved credential.") from exc

    def has(self, provider: str) -> bool:
        return self.get(provider) is not None

    @staticmethod
    def _validate(provider: str) -> None:
        if not provider or not provider.replace("_", "").replace("-", "").isalnum():
            raise ValueError("Invalid credential provider id")

    @staticmethod
    def _keyring():
        try:
            import keyring
            backend = keyring.get_keyring()
            name = f"{type(backend).__module__}.{type(backend).__name__}".lower()
            if ".fail." in name or ".null." in name:
                raise CredentialError("Secure credential storage is unavailable.")
            return keyring
        except CredentialError:
            raise
        except Exception as exc:
            raise CredentialError("Secure credential storage is unavailable.") from exc
