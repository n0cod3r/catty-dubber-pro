from catty_engine.settings.credentials import CredentialStore
from catty_engine.translation.credentials import CredentialPool


class Store(CredentialStore):
    def __init__(self):
        self.values = {("gemini", "one"): "key-one", ("gemini", "two"): "key-two"}

    def get(self, provider: str, credential_id: str = "default") -> str | None:
        return self.values.get((provider, credential_id))


def test_pool_skips_rate_limited_credential():
    pool = CredentialPool("gemini", Store(), ["one", "two"])
    assert [item.id for item in pool.available()] == ["one", "two"]
    pool.cooldown("one", 60)
    assert [item.id for item in pool.available()] == ["two"]


def test_pool_skips_invalid_credential():
    pool = CredentialPool("gemini", Store(), ["one", "two"])
    pool.mark_invalid("one")
    assert [item.id for item in pool.available()] == ["two"]
