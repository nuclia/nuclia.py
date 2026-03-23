"""Tests for NucliaAuth HTTP methods using respx."""
import pytest
import httpx
import respx
from unittest.mock import MagicMock, patch

from nuclia.sdk.auth import NucliaAuth
from nuclia.lib.utils import build_httpx_client
from nuclia.exceptions import UserTokenExpired

GLOBAL_BASE = "https://rag.progress.cloud"
USER_ENDPOINT = "/api/v1/user/welcome"
ACCOUNTS_ENDPOINT = "/api/v1/accounts"
ZONES_ENDPOINT = "/api/v1/zones"


def make_auth(token: str = "my-user-token") -> NucliaAuth:
    auth = NucliaAuth.__new__(NucliaAuth)
    auth.client = build_httpx_client()
    mock_config = MagicMock()
    mock_config.token = token
    mock_config.accounts = []
    mock_config.zones = []
    auth._inner_config = mock_config
    return auth


# ── _validate_user_token ──────────────────────────────────────────────────────


def test_validate_user_token_returns_true_on_200():
    auth = make_auth()
    with respx.mock(base_url=GLOBAL_BASE) as mock:
        mock.get(USER_ENDPOINT).mock(return_value=httpx.Response(200, json={}))
        result = auth._validate_user_token(code="valid-token")
    assert result is True


def test_validate_user_token_returns_false_on_401():
    auth = make_auth()
    with respx.mock(base_url=GLOBAL_BASE) as mock:
        mock.get(USER_ENDPOINT).mock(return_value=httpx.Response(401, text="Unauthorized"))
        result = auth._validate_user_token(code="bad-token")
    assert result is False


def test_validate_user_token_uses_config_token_when_no_code():
    auth = make_auth(token="config-token")
    with respx.mock(base_url=GLOBAL_BASE) as mock:
        route = mock.get(USER_ENDPOINT).mock(return_value=httpx.Response(200, json={}))
        result = auth._validate_user_token()
    assert result is True
    assert "config-token" in route.calls[0].request.headers["authorization"]


# ── _request ─────────────────────────────────────────────────────────────────


def test_request_raises_need_user_token_when_no_token():
    from nuclia.exceptions import NeedUserToken
    auth = make_auth()
    auth._config.token = None
    with pytest.raises(NeedUserToken):
        auth._request("GET", GLOBAL_BASE + ACCOUNTS_ENDPOINT)


def test_request_returns_json_on_success():
    auth = make_auth()
    with respx.mock(base_url=GLOBAL_BASE) as mock:
        mock.get(ACCOUNTS_ENDPOINT).mock(
            return_value=httpx.Response(200, json=[{"slug": "acct1", "id": "1", "title": "Acct 1", "type": "stash-basic"}])
        )
        result = auth._request("GET", GLOBAL_BASE + ACCOUNTS_ENDPOINT)
    assert isinstance(result, list)
    assert result[0]["slug"] == "acct1"


def test_request_returns_none_on_204():
    auth = make_auth()
    with respx.mock(base_url=GLOBAL_BASE) as mock:
        mock.delete("/api/v1/tokens/tok-1").mock(return_value=httpx.Response(204))
        result = auth._request("DELETE", GLOBAL_BASE + "/api/v1/tokens/tok-1")
    assert result is None


def test_request_raises_user_token_expired_on_403():
    auth = make_auth()
    with respx.mock(base_url=GLOBAL_BASE) as mock:
        mock.get(ACCOUNTS_ENDPOINT).mock(return_value=httpx.Response(403, text="Forbidden"))
        with pytest.raises(UserTokenExpired):
            auth._request("GET", GLOBAL_BASE + ACCOUNTS_ENDPOINT)


def test_request_raises_on_500():
    auth = make_auth()
    with respx.mock(base_url=GLOBAL_BASE) as mock:
        mock.get(ACCOUNTS_ENDPOINT).mock(return_value=httpx.Response(500, text="Server error"))
        with pytest.raises(Exception):
            auth._request("GET", GLOBAL_BASE + ACCOUNTS_ENDPOINT)


# ── accounts ─────────────────────────────────────────────────────────────────


def test_accounts_returns_account_list():
    from nuclia.config import Account
    auth = make_auth()
    accounts_data = [{"slug": "acct1", "id": "1", "title": "Acct 1", "type": "stash-basic"}]
    with respx.mock(base_url=GLOBAL_BASE) as mock:
        mock.get(ACCOUNTS_ENDPOINT).mock(
            return_value=httpx.Response(200, json=accounts_data)
        )
        result = auth.accounts()
    assert len(result) == 1
    assert result[0].slug == "acct1"


def test_accounts_returns_empty_on_none():
    auth = make_auth()
    with respx.mock(base_url=GLOBAL_BASE) as mock:
        mock.get(ACCOUNTS_ENDPOINT).mock(return_value=httpx.Response(204))
        result = auth.accounts()
    assert result == []


# ── zones ─────────────────────────────────────────────────────────────────────


def test_zones_returns_zone_list():
    auth = make_auth()
    zones_data = [{"slug": "europe-1", "id": "z1", "title": "Europe 1"}]
    with respx.mock(base_url=GLOBAL_BASE) as mock:
        mock.get(ZONES_ENDPOINT).mock(return_value=httpx.Response(200, json=zones_data))
        result = auth.zones()
    assert len(result) == 1
    assert result[0].slug == "europe-1"
