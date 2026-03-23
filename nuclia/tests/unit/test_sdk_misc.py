"""Tests for NucliaAccounts, NucliaZones, NucliaDB — inject mock auth/ndb."""
from unittest.mock import MagicMock, patch

import pytest
from nucliadb_models.resource import KnowledgeBoxList

from nuclia.config import Account, Config, Selection
from nuclia.sdk.accounts import NucliaAccounts
from nuclia.sdk.zones import NucliaZones
from nuclia.sdk.nucliadb import NucliaDB


def _accounts_with_config(config: Config) -> NucliaAccounts:
    obj = NucliaAccounts()
    mock_auth = MagicMock()
    mock_auth._config = config
    mock_auth.accounts.return_value = []
    with patch("nuclia.sdk.accounts.get_auth", return_value=mock_auth):
        pass
    obj.__class__._auth = property(lambda self: mock_auth)
    return obj, mock_auth


# ── NucliaAccounts ────────────────────────────────────────────────────────────


def test_accounts_list():
    mock_auth = MagicMock()
    mock_auth.accounts.return_value = [Account(id="acc-1", title="T", slug="s")]
    with patch("nuclia.sdk.accounts.get_auth", return_value=mock_auth):
        result = NucliaAccounts().list()
    assert len(result) == 1


def test_accounts_default_sets_account():
    config = Config(accounts=[Account(id="acc-1", title="T", slug="my-account")])
    mock_auth = MagicMock()
    mock_auth._config = config
    with patch("nuclia.sdk.accounts.get_auth", return_value=mock_auth):
        with patch("nuclia.config.Config.save"):
            NucliaAccounts().default("my-account")
    assert config.default.account == "my-account"


def test_accounts_default_raises_when_not_found():
    config = Config(accounts=[])
    mock_auth = MagicMock()
    mock_auth._config = config
    with patch("nuclia.sdk.accounts.get_auth", return_value=mock_auth):
        with pytest.raises(KeyError):
            NucliaAccounts().default("missing")


# ── NucliaZones ───────────────────────────────────────────────────────────────


def test_zones_list():
    mock_auth = MagicMock()
    mock_auth.zones.return_value = ["zone-1"]
    with patch("nuclia.sdk.zones.get_auth", return_value=mock_auth):
        result = NucliaZones().list()
    assert result == ["zone-1"]


def test_zones_default():
    config = Config()
    mock_auth = MagicMock()
    mock_auth._config = config
    with patch("nuclia.sdk.zones.get_auth", return_value=mock_auth):
        with patch("nuclia.config.Config.save"):
            NucliaZones().default("eu-1")
    assert config.default.zone == "eu-1"


# ── NucliaDB ──────────────────────────────────────────────────────────────────


def test_nucliadb_list():
    mock_ndb_client = MagicMock()
    mock_ndb_client.ndb.list_knowledge_boxes.return_value = KnowledgeBoxList()
    result = NucliaDB().list(ndb=mock_ndb_client)
    assert isinstance(result, KnowledgeBoxList)


def test_nucliadb_delete():
    mock_ndb_client = MagicMock()
    mock_auth = MagicMock()
    with patch("nuclia.sdk.nucliadb.get_auth", return_value=mock_auth):
        NucliaDB().delete(kbid="kb-1", ndb=mock_ndb_client)
    mock_ndb_client.ndb.delete_knowledge_box.assert_called_once_with(kbid="kb-1")
    mock_auth.unset_kb.assert_called_once_with(kbid="kb-1")
