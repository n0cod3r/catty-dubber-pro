"""Secure provider credentials stored in the operating-system keychain."""

from __future__ import annotations

SERVICE_NAME = "Catty Dubber Pro"
DEFAULT_CREDENTIAL_ID = "default"


class CredentialError(RuntimeError):
    """Credential storage is unavailable or failed."""


class CredentialStore:
    """OS-keychain-only credential storage for macOS and Windows."""

    @staticmethod
    def _account(provider: str, credential_id: str) -> str:
        CredentialStore._validate(provider)
        CredentialStore._validate(credential_id)
        # Preserve the original account name for backwards compatibility.
        return provider if credential_id == DEFAULT_CREDENTIAL_ID else f"{provider}:{credential_id}"

    def get(self, provider: str, credential_id: str = DEFAULT_CREDENTIAL_ID) -> str | None:
        account = self._account(provider, credential_id)
        try:
            value = self._keyring().get_password(SERVICE_NAME, account)
        except CredentialError:
            raise
        except Exception as exc:
            raise CredentialError("Secure credential storage is unavailable.") from exc
        return value.strip() if value else None

    def set(self, provider: str, secret: str, credential_id: str = DEFAULT_CREDENTIAL_ID) -> None:
        account = self._account(provider, credential_id)
        secret = secret.strip()
        if not secret:
            raise ValueError("Credential must not be empty")
        try:
            self._keyring().set_password(SERVICE_NAME, account, secret)
        except CredentialError:
            raise
        except Exception as exc:
            raise CredentialError("Could not save the credential securely.") from exc

    def delete(self, provider: str, credential_id: str = DEFAULT_CREDENTIAL_ID) -> None:
        account = self._account(provider, credential_id)
        try:
            self._keyring().delete_password(SERVICE_NAME, account)
        except CredentialError:
            raise
        except Exception as exc:
            if exc.__class__.__name__ != "PasswordDeleteError":
                raise CredentialError("Could not remove the saved credential.") from exc

    def has(self, provider: str, credential_id: str = DEFAULT_CREDENTIAL_ID) -> bool:
        try:
            return self.get(provider, credential_id) is not None
        except CredentialError:
            return False

    @staticmethod
    def _validate(value: str) -> None:
        normalized = value.replace("_", "").replace("-", "")
        if not value or not normalized.isalnum():
            raise ValueError("Invalid credential id")

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
