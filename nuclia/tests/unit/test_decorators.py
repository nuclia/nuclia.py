"""Tests for decorators: pretty, zone, nucliadb, kb (ndb bypass), nua (nc bypass)."""
import pytest
from unittest.mock import MagicMock, patch

from nuclia.config import Config, NuaKey, Selection
from nuclia.decorators import pretty, zone, nucliadb, kb, nua
from nuclia.exceptions import NotDefinedDefault


# ── pretty decorator ──────────────────────────────────────────────────────────


def test_pretty_returns_result_by_default():
    @pretty
    def my_func(**kwargs):
        return {"key": "value"}

    result = my_func()
    assert result == {"key": "value"}


def test_pretty_returns_yaml_when_requested():
    @pretty
    def my_func(**kwargs):
        return {"key": "value"}

    result = my_func(yaml=True)
    assert "key" in result
    assert "value" in result


def test_pretty_returns_json_when_requested():
    @pretty
    def my_func(**kwargs):
        m = MagicMock()
        m.json.return_value = '{"a": 1}'
        return m

    result = my_func(json=True)
    assert result == '{"a": 1}'


@pytest.mark.asyncio
async def test_pretty_async_returns_result():
    @pretty
    async def my_async_func(**kwargs):
        return {"key": "value"}

    result = await my_async_func()
    assert result == {"key": "value"}


@pytest.mark.asyncio
async def test_pretty_async_returns_json():
    @pretty
    async def my_async_func(**kwargs):
        m = MagicMock()
        m.json.return_value = '{"x": 2}'
        return m

    result = await my_async_func(json=True)
    assert result == '{"x": 2}'


# ── zone decorator ────────────────────────────────────────────────────────────


def test_zone_passes_existing_zone():
    @zone
    def my_func(**kwargs):
        return kwargs.get("zone")

    with patch("nuclia.decorators.get_auth") as mock_get_auth:
        result = my_func(zone="us-1")
    assert result == "us-1"
    mock_get_auth.assert_not_called()


def test_zone_fetches_default_zone_when_not_provided():
    @zone
    def my_func(**kwargs):
        return kwargs.get("zone")

    mock_auth = MagicMock()
    mock_auth._config.get_default_zone.return_value = "eu-1"
    with patch("nuclia.decorators.get_auth", return_value=mock_auth):
        result = my_func()
    assert result == "eu-1"


# ── kb decorator (bypass via ndb=) ────────────────────────────────────────────


def test_kb_bypassed_when_ndb_provided():
    @kb
    def my_func(**kwargs):
        return kwargs["ndb"]

    mock_ndb = MagicMock()
    result = my_func(ndb=mock_ndb)
    assert result is mock_ndb


@pytest.mark.asyncio
async def test_kb_async_bypassed_when_ndb_provided():
    @kb
    async def my_async_func(**kwargs):
        return kwargs["ndb"]

    mock_ndb = MagicMock()
    result = await my_async_func(ndb=mock_ndb)
    assert result is mock_ndb


# ── nua decorator (bypass via nc=) ────────────────────────────────────────────


def test_nua_bypassed_when_nc_provided():
    @nua
    def my_func(**kwargs):
        return kwargs["nc"]

    mock_nc = MagicMock()
    result = my_func(nc=mock_nc)
    assert result is mock_nc


@pytest.mark.asyncio
async def test_nua_async_bypassed_when_nc_provided():
    @nua
    async def my_async_func(**kwargs):
        return kwargs["nc"]

    mock_nc = MagicMock()
    result = await my_async_func(nc=mock_nc)
    assert result is mock_nc


# ── nucliadb decorator ────────────────────────────────────────────────────────


def test_nucliadb_bypassed_when_ndb_provided():
    @nucliadb
    def my_func(**kwargs):
        return kwargs["ndb"]

    mock_ndb = MagicMock()
    result = my_func(ndb=mock_ndb)
    assert result is mock_ndb


def test_nucliadb_uses_url_when_provided():
    @nucliadb
    def my_func(**kwargs):
        return kwargs["ndb"]

    with patch("nuclia.decorators.NucliaDBClient") as MockClient:
        MockClient.return_value = MagicMock()
        result = my_func(url="http://localhost:8080")
    MockClient.assert_called_once()


def test_nucliadb_raises_when_no_url_and_no_default():
    @nucliadb
    def my_func(**kwargs):
        return kwargs["ndb"]

    mock_auth = MagicMock()
    mock_auth._config.get_default_nucliadb.side_effect = NotDefinedDefault()
    with patch("nuclia.decorators.get_auth", return_value=mock_auth):
        with pytest.raises(NotDefinedDefault):
            my_func()
