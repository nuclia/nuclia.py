"""Tests for nuclia/data.py — get_config, get_client, get_auth."""
from unittest.mock import MagicMock, patch

import pytest

from nuclia.config import Config, KnowledgeBox, Selection
from nuclia.data import DataConfig, get_config, set_config
from nuclia.exceptions import KBNotAvailable


def _fresh_data():
    """Return a fresh DataConfig and patch the module-level DATA."""
    return DataConfig()


# ── set_config / get_config ───────────────────────────────────────────────────


def test_set_config_stores_config():
    import nuclia.data as data_mod
    original = data_mod.DATA.config
    config = Config()
    set_config(config)
    assert data_mod.DATA.config is config
    # restore
    data_mod.DATA.config = original


def test_get_config_returns_existing():
    import nuclia.data as data_mod
    config = Config()
    original = data_mod.DATA.config
    data_mod.DATA.config = config
    result = get_config()
    assert result is config
    data_mod.DATA.config = original


def test_get_config_reads_from_file_when_none():
    import nuclia.data as data_mod
    original = data_mod.DATA.config
    data_mod.DATA.config = None
    fresh = Config()
    with patch("nuclia.config.read_config", return_value=fresh) as mock_read:
        result = get_config()
    assert result is fresh
    mock_read.assert_called_once()
    data_mod.DATA.config = original


# ── get_client ────────────────────────────────────────────────────────────────


def test_get_client_raises_when_kb_not_found():
    from nuclia.data import get_client
    import nuclia.data as data_mod

    config = Config(kbs_token=[], kbs=[])
    mock_auth = MagicMock()
    mock_auth._config = config

    original = data_mod.DATA.auth
    data_mod.DATA.auth = mock_auth
    original_config = data_mod.DATA.config
    data_mod.DATA.config = config

    with pytest.raises((KBNotAvailable, Exception)):
        get_client("nonexistent-kb")

    data_mod.DATA.auth = original
    data_mod.DATA.config = original_config


def test_get_client_oss_returns_client():
    from nuclia.data import get_client
    from nuclia.lib.kb import NucliaDBClient, Environment
    import nuclia.data as data_mod

    kb = KnowledgeBox(id="kb-oss", url="http://localhost:8080", region=None)
    config = Config(kbs_token=[kb])

    mock_auth = MagicMock()
    mock_auth._config = config
    mock_auth._validate_user_token.return_value = False

    original_auth = data_mod.DATA.auth
    original_config = data_mod.DATA.config
    data_mod.DATA.auth = mock_auth
    data_mod.DATA.config = config

    with patch("nuclia.data.NucliaDBClient") as MockNDB:
        MockNDB.return_value = MagicMock()
        result = get_client("kb-oss")

    MockNDB.assert_called_once()
    call_kwargs = MockNDB.call_args[1]
    assert call_kwargs["environment"] == Environment.OSS

    data_mod.DATA.auth = original_auth
    data_mod.DATA.config = original_config


def test_get_client_cloud_with_token():
    from nuclia.data import get_client
    from nuclia.lib.kb import Environment
    import nuclia.data as data_mod

    kb = KnowledgeBox(id="kb-cloud", url="https://eu.nuclia.cloud/kb/kb-cloud", region="eu", token="api-key")
    config = Config(kbs_token=[kb])

    mock_auth = MagicMock()
    mock_auth._config = config

    original_auth = data_mod.DATA.auth
    original_config = data_mod.DATA.config
    data_mod.DATA.auth = mock_auth
    data_mod.DATA.config = config

    with patch("nuclia.data.NucliaDBClient") as MockNDB:
        MockNDB.return_value = MagicMock()
        get_client("kb-cloud")

    call_kwargs = MockNDB.call_args[1]
    assert call_kwargs["environment"] == Environment.CLOUD
    assert call_kwargs["api_key"] == "api-key"

    data_mod.DATA.auth = original_auth
    data_mod.DATA.config = original_config
