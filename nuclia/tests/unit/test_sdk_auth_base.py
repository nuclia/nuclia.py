"""Tests for BaseNucliaAuth, print_config, print_nuas, and _extract_account."""
import base64
import json
import time
from unittest.mock import MagicMock, patch

import pytest

from nuclia.config import Account, Config, KnowledgeBox, NuaKey, RetrievalAgentOrchestrator, Selection
from nuclia.sdk.auth import BaseNucliaAuth, NucliaAuth, print_config, print_nuas


def _make_jwt(payload: dict) -> str:
    """Build a minimal fake JWT with the given payload."""
    header = base64.urlsafe_b64encode(b'{"alg":"HS256"}').decode().rstrip("=")
    encoded = base64.urlsafe_b64encode(json.dumps(payload).encode()).decode().rstrip("=")
    return f"{header}.{encoded}.fakesig"


# ── BaseNucliaAuth ────────────────────────────────────────────────────────────


def _auth_with_config(config: Config) -> BaseNucliaAuth:
    auth = BaseNucliaAuth()
    auth._inner_config = config
    return auth


def test_base_auth_get_account_id_found():
    config = Config(accounts=[Account(id="acc-id", title="Test", slug="my-account")])
    auth = _auth_with_config(config)
    assert auth.get_account_id("my-account") == "acc-id"


def test_base_auth_get_account_id_not_found():
    config = Config(accounts=[])
    auth = _auth_with_config(config)
    with pytest.raises(ValueError, match="not found"):
        auth.get_account_id("missing")


def test_base_auth_list_nuas():
    nua = NuaKey(client_id="nua-1", account_type=None, region="eu", account="acc", token="tok")
    config = Config(nuas_token=[nua])
    auth = _auth_with_config(config)
    result = auth.list_nuas()
    assert len(result) == 1
    assert result[0].client_id == "nua-1"


def test_base_auth_list_nuas_empty():
    config = Config()
    auth = _auth_with_config(config)
    assert auth.list_nuas() == []


def test_base_auth_default_nua():
    nua = NuaKey(client_id="nua-1", account_type=None, region="eu", account="acc", token="tok")
    config = Config(nuas_token=[nua])
    auth = _auth_with_config(config)
    with patch("nuclia.config.Config.save"):
        auth.default_nua("nua-1")
    assert config.default.nua == "nua-1"


def test_base_auth_default_nua_not_found():
    config = Config(nuas_token=[])
    auth = _auth_with_config(config)
    with pytest.raises(KeyError):
        auth.default_nua("missing")


def test_base_auth_default_kb():
    config = Config()
    auth = _auth_with_config(config)
    with patch("nuclia.config.Config.save"):
        auth.default_kb("kb-1")
    assert config.default.kbid == "kb-1"


def test_base_auth_unset_kb():
    config = Config()
    with patch("nuclia.config.Config.save"):
        config.set_default_kb("kb-1")
    auth = _auth_with_config(config)
    with patch("nuclia.config.Config.save"):
        auth.unset_kb("kb-1")
    assert config.default.kbid is None


# ── _extract_account ─────────────────────────────────────────────────────────


def test_extract_account():
    token = _make_jwt({"jti": "account-uuid-123", "exp": int(time.time()) + 3600})
    auth = NucliaAuth.__new__(NucliaAuth)
    result = auth._extract_account(token)
    assert result == "account-uuid-123"


def test_extract_account_missing_jti():
    token = _make_jwt({"sub": "other", "exp": int(time.time()) + 3600})
    auth = NucliaAuth.__new__(NucliaAuth)
    result = auth._extract_account(token)
    assert result is None


# ── print_config ──────────────────────────────────────────────────────────────


def test_print_config_with_defaults(capsys):
    kb = KnowledgeBox(id="kb-1", url="http://localhost", region=None)
    config = Config(
        kbs_token=[kb],
        default=Selection(account="my-account", kbid="kb-1"),
    )
    print_config(config)
    captured = capsys.readouterr()
    assert "my-account" in captured.out


def test_print_config_empty_default(capsys):
    config = Config(default=None)
    print_config(config)
    captured = capsys.readouterr()
    assert captured.out == ""


def test_print_config_with_agent(capsys):
    agent = RetrievalAgentOrchestrator(id="agent-1", account="acc", region="us-1")
    config = Config(
        agents=[agent],
        default=Selection(agent_id="agent-1"),
    )
    print_config(config)
    captured = capsys.readouterr()
    assert "agent-1" in captured.out or "us-1" in captured.out


# ── print_nuas ────────────────────────────────────────────────────────────────


def test_print_nuas_with_keys(capsys):
    nua = NuaKey(client_id="nua-1", account_type=None, region="eu", account="acc", token="tok")
    config = Config(nuas_token=[nua])
    print_nuas(config)
    captured = capsys.readouterr()
    assert "nua-1" in captured.out


def test_print_nuas_with_default(capsys):
    nua = NuaKey(client_id="nua-1", account_type=None, region="eu", account="acc", token="tok")
    config = Config(nuas_token=[nua], default=Selection(nua="nua-1"))
    print_nuas(config)
    captured = capsys.readouterr()
    assert "nua-1" in captured.out


def test_print_nuas_empty(capsys):
    config = Config()
    print_nuas(config)
    captured = capsys.readouterr()
    assert captured.out == ""
