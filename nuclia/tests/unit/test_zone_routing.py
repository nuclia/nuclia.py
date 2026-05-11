from nuclia import BASE_DOMAIN, get_regional_url
from nuclia.config import Config, NuaKey, Selection, Zone
from nuclia.sdk.auth import BaseNucliaAuth


class _FakeAuth(BaseNucliaAuth):
    def __init__(self, config: Config):
        self._inner_config = config


def test_get_regional_url_with_zone_slug():
    assert (
        get_regional_url("europe-1", "/api/v1")
        == f"https://europe-1.{BASE_DOMAIN}/api/v1"
    )


def test_get_regional_url_with_origin():
    assert (
        get_regional_url(
            "europe-1",
            "/api/v1",
            origin_url="https://private.example.com/",
        )
        == "https://private.example.com/api/v1"
    )


def test_resolve_zone_endpoint_prefers_origin_from_zones_cache():
    config = Config(
        token="user-token",
        zones=[
            Zone(
                id="zone-id",
                title="Private Zone",
                slug="private-zone",
                private=True,
                origin="https://private.example.com",
            )
        ],
    )
    auth = _FakeAuth(config)

    assert auth.resolve_zone_endpoint("private-zone") == (
        "private-zone",
        "https://private.example.com",
    )


def test_resolve_zone_endpoint_uses_zone_id_when_slug_missing():
    config = Config(
        token="user-token",
        zones=[
            Zone(
                id="zone-id",
                title="Private Zone",
                slug=None,
                private=True,
                origin="https://private.example.com",
            )
        ],
    )
    auth = _FakeAuth(config)

    assert auth.resolve_zone_endpoint("zone-id") == (
        "zone-id",
        "https://private.example.com",
    )


def test_nua_key_origin_overrides_issuer():
    # When NuaKey.origin is set it should be preferred over NuaKey.region (the issuer URL)
    # for any consumer that does `nua_obj.origin or nua_obj.region` (e.g. kbs_nua).
    key = NuaKey(
        client_id="client",
        account_type=None,
        region="https://auth.private.corp",
        account="account",
        token="token",
        origin="https://api.private.corp",
    )
    assert (key.origin or key.region) == "https://api.private.corp"


def test_nua_key_origin_falls_back_to_issuer_when_unset():
    key = NuaKey(
        client_id="client",
        account_type=None,
        region="https://private.example.com",
        account="account",
        token="token",
    )
    assert (key.origin or key.region) == "https://private.example.com"


def test_resolve_zone_endpoint_parses_origin_input():
    config = Config(token="user-token")
    auth = _FakeAuth(config)

    assert auth.resolve_zone_endpoint("https://private.example.com/") == (
        "private",
        "https://private.example.com",
    )
