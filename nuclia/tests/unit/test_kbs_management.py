import pytest

from nuclia.decorators import zone
from nuclia.sdk.kbs import NucliaKBS


class _FakeConfig:
    token = None

    def get_default_zone(self):
        return "europe-1"

    def get_default_nua(self):
        return "default-nua"

    def get_nua(self, _nua_id):
        class _NuaObj:
            region = "https://europe-1.dp.progress.cloud"

        return _NuaObj()


class _FakeAuth:
    def __init__(self):
        self._config = _FakeConfig()


@zone
def _decorated_with_zone(slug: str, zone: str = "europe-1"):
    return slug, zone


def test_zone_decorator_does_not_duplicate_positional_zone(monkeypatch):
    monkeypatch.setattr("nuclia.decorators.get_auth", lambda: _FakeAuth())

    slug, zone_name = _decorated_with_zone("my-kb", "us-1")

    assert slug == "my-kb"
    assert zone_name == "us-1"


def test_kbs_resolve_zone_from_nua_when_missing(monkeypatch):
    monkeypatch.setattr("nuclia.sdk.kbs.get_auth", lambda: _FakeAuth())

    kbs = NucliaKBS()

    assert kbs._resolve_management_zone(None) == "europe-1"


def test_kbs_reject_mismatched_zone_for_nua(monkeypatch):
    monkeypatch.setattr("nuclia.sdk.kbs.get_auth", lambda: _FakeAuth())

    kbs = NucliaKBS()

    with pytest.raises(ValueError, match="NUA key is scoped to zone"):
        kbs._resolve_management_zone("us-1")
