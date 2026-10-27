from catty_engine.settings.credentials import CredentialStore


class FakeKeyring:
    def __init__(self):
        self.values = {}
    def get_password(self, service, provider):
        return self.values.get((service, provider))
    def set_password(self, service, provider, secret):
        self.values[(service, provider)] = secret
    def delete_password(self, service, provider):
        self.values.pop((service, provider), None)


def test_credential_round_trip_without_exposing_storage(monkeypatch):
    backend = FakeKeyring()
    monkeypatch.setattr(CredentialStore, "_keyring", staticmethod(lambda: backend))
    store = CredentialStore()
    assert store.has("gemini") is False
    store.set("gemini", " secret ")
    assert store.has("gemini") is True
    assert store.get("gemini") == "secret"
    store.delete("gemini")
    assert store.has("gemini") is False
