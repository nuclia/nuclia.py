import pytest
from unittest.mock import MagicMock, patch

from nuclia.config import (
    Account,
    Config,
    KnowledgeBox,
    NuaKey,
    RetrievalAgentOrchestrator,
    Selection,
    Zone,
    retrieve_account,
    retrieve_nua,
)
from nuclia.exceptions import NotDefinedDefault


# --- Model __str__ tests ---


def test_knowledge_box_str_with_region():
    kb = KnowledgeBox(id="kb-id", url="https://europe-1.nuclia.cloud", region="europe-1")
    result = str(kb)
    assert "europe-1" in result
    assert "kb-id" in result


def test_knowledge_box_str_without_region():
    kb = KnowledgeBox(id="kb-id", url="http://localhost:8080")
    result = str(kb)
    assert "LOCAL" in result


def test_knowledge_box_str_with_account_and_slug():
    kb = KnowledgeBox(
        id="kb-id",
        url="https://europe-1.nuclia.cloud",
        region="europe-1",
        account="my-account",
        slug="my-kb",
    )
    result = str(kb)
    assert "my-account" in result
    assert "my-kb" in result


def test_retrieval_agent_orchestrator_str_with_memory():
    agent = RetrievalAgentOrchestrator(
        id="agent-id", account="acc", region="us-1", memory=True
    )
    result = str(agent)
    assert "with Memory" in result
    assert "us-1" in result


def test_retrieval_agent_orchestrator_str_without_memory():
    agent = RetrievalAgentOrchestrator(
        id="agent-id", account="acc", region="us-1", memory=False
    )
    result = str(agent)
    assert "without Memory" in result


def test_nua_key_str():
    key = NuaKey(
        client_id="client-1",
        account_type="STASH-TRIAL",
        region="europe-1",
        account="my-account",
        token="tok",
    )
    result = str(key)
    assert "client-1" in result
    assert "my-account" in result


def test_zone_str():
    zone = Zone(id="zone-id", title="Europe 1", slug="europe-1")
    result = str(zone)
    assert "zone-id" in result
    assert "europe-1" in result


def test_account_str():
    account = Account(id="acc-id", title="My Account", slug="my-account")
    result = str(account)
    assert "acc-id" in result
    assert "my-account" in result


# --- Config.get_kb ---


def test_config_get_kb_from_kbs_token():
    config = Config()
    config.kbs_token = [KnowledgeBox(id="kb-1", url="http://localhost")]
    result = config.get_kb("kb-1")
    assert result is not None
    assert result.id == "kb-1"


def test_config_get_kb_from_kbs_fallback():
    config = Config()
    config.kbs_token = []
    config.kbs = [KnowledgeBox(id="kb-2", url="http://localhost")]
    result = config.get_kb("kb-2")
    assert result is not None
    assert result.id == "kb-2"


# --- Config.get_agent ---


def test_config_get_agent_from_agents_token():
    config = Config()
    config.agents_token = [
        RetrievalAgentOrchestrator(id="agent-1", account="acc", region="us-1")
    ]
    result = config.get_agent("agent-1")
    assert result is not None
    assert result.id == "agent-1"


def test_config_get_agent_from_agents_fallback():
    config = Config()
    config.agents_token = []
    config.agents = [
        RetrievalAgentOrchestrator(id="agent-2", account="acc", region="us-1")
    ]
    result = config.get_agent("agent-2")
    assert result is not None
    assert result.id == "agent-2"


def test_config_get_agent_not_found_returns_none():
    config = Config()
    config.agents_token = []
    config.agents = []
    result = config.get_agent("missing")
    assert result is None


# --- Config.get_nua ---


def test_config_get_nua():
    config = Config()
    config.nuas_token = [
        NuaKey(client_id="nua-1", account_type=None, region="eu", account="acc", token="tok")
    ]
    result = config.get_nua("nua-1")
    assert result.client_id == "nua-1"


# --- Config token / default setters ---


def test_config_set_and_remove_user_token():
    config = Config()
    with patch("nuclia.config.Config.save"):
        config.set_user_token("my-token")
        assert config.token == "my-token"
        config.remove_user_token()
        assert config.token is None


def test_config_set_nua_token_new():
    config = Config()
    with patch("nuclia.config.Config.save"):
        config.set_nua_token("nua-1", "acc", "eu", "tok")
    assert len(config.nuas_token) == 1
    assert config.nuas_token[0].client_id == "nua-1"


def test_config_set_nua_token_updates_existing():
    config = Config()
    config.nuas_token = [
        NuaKey(client_id="nua-1", account_type=None, region="eu", account="acc", token="old")
    ]
    with patch("nuclia.config.Config.save"):
        config.set_nua_token("nua-1", "acc", "eu", "new-tok")
    assert len(config.nuas_token) == 1
    assert config.nuas_token[0].token == "new-tok"


def test_config_set_kb_token():
    config = Config()
    with patch("nuclia.config.Config.save"):
        config.set_kb_token("https://europe-1.nuclia.cloud/api/v1/kb/kb-1", "kb-1", "token-1", "My KB")
    assert len(config.kbs_token) == 1
    assert config.kbs_token[0].id == "kb-1"


def test_config_del_kbid():
    config = Config()
    config.kbs_token = [KnowledgeBox(id="kb-1", url="http://localhost")]
    config._del_kbid("kb-1")
    assert len(config.kbs_token) == 0


def test_config_set_agent_token():
    config = Config()
    with patch("nuclia.config.Config.save"):
        config.set_agent_token("us-1", "agent-1", True, "acc-id", "token", "My Agent")
    assert len(config.agents_token) == 1
    assert config.agents_token[0].id == "agent-1"


def test_config_set_agent_token_updates_existing():
    config = Config()
    config.agents_token = [
        RetrievalAgentOrchestrator(id="agent-1", account="acc", region="us-1", token="old")
    ]
    with patch("nuclia.config.Config.save"):
        config.set_agent_token("us-1", "agent-1", True, "acc", "new-token")
    assert len(config.agents_token) == 1
    assert config.agents_token[0].token == "new-token"


# --- Default getters/setters ---


def test_config_default_kb():
    config = Config()
    with patch("nuclia.config.Config.save"):
        config.set_default_kb("kb-1")
    assert config.get_default_kb() == "kb-1"


def test_config_get_default_kb_raises_when_unset():
    config = Config(default=None)
    with pytest.raises(NotDefinedDefault):
        config.get_default_kb()


def test_config_unset_default_kb():
    config = Config()
    with patch("nuclia.config.Config.save"):
        config.set_default_kb("kb-1")
        config.unset_default_kb("kb-1")
    assert config.default.kbid is None


def test_config_unset_default_kb_different_id_leaves_unchanged():
    config = Config()
    with patch("nuclia.config.Config.save"):
        config.set_default_kb("kb-1")
        config.unset_default_kb("kb-2")
    assert config.default.kbid == "kb-1"


def test_config_default_agent():
    config = Config()
    with patch("nuclia.config.Config.save"):
        config.set_default_agent("agent-1")
    assert config.get_default_agent() == "agent-1"


def test_config_get_default_agent_raises_when_unset():
    config = Config(default=None)
    with pytest.raises(NotDefinedDefault):
        config.get_default_agent()


def test_config_unset_default_agent():
    config = Config()
    with patch("nuclia.config.Config.save"):
        config.set_default_agent("agent-1")
        config.unset_default_agent("agent-1")
    assert config.default.agent_id is None


def test_config_default_nua():
    config = Config()
    with patch("nuclia.config.Config.save"):
        config.set_default_nua("nua-1")
    assert config.get_default_nua() == "nua-1"


def test_config_get_default_nua_raises_when_unset():
    config = Config(default=None)
    with pytest.raises(NotDefinedDefault):
        config.get_default_nua()


def test_config_default_account():
    config = Config()
    with patch("nuclia.config.Config.save"):
        config.set_default_account("my-account")
    assert config.get_default_account() == "my-account"


def test_config_get_default_account_raises_when_unset():
    config = Config(default=None)
    with pytest.raises(NotDefinedDefault):
        config.get_default_account()


def test_config_default_zone():
    config = Config()
    with patch("nuclia.config.Config.save"):
        config.set_default_zone("eu-1")
    assert config.get_default_zone() == "eu-1"


def test_config_get_default_zone_returns_none_when_unset():
    config = Config(default=None)
    assert config.get_default_zone() is None


def test_config_default_nucliadb():
    config = Config()
    with patch("nuclia.config.Config.save"):
        config.set_default_nucliadb("http://localhost:8080")
    assert config.get_default_nucliadb() == "http://localhost:8080"


def test_config_get_default_nucliadb_raises_when_unset():
    config = Config(default=None)
    with pytest.raises(NotDefinedDefault):
        config.get_default_nucliadb()


# --- retrieve helpers ---


def test_retrieve_nua_found():
    nua = NuaKey(client_id="nua-1", account_type=None, region="eu", account="acc", token="tok")
    result = retrieve_nua([nua], "nua-1")
    assert result is not None
    assert result.client_id == "nua-1"


def test_retrieve_nua_not_found():
    result = retrieve_nua([], "nua-1")
    assert result is None


def test_retrieve_account_found():
    account = Account(id="acc-1", title="My Account", slug="my-account")
    result = retrieve_account([account], "my-account")
    assert result is not None
    assert result.id == "acc-1"


def test_retrieve_account_not_found():
    result = retrieve_account([], "missing")
    assert result is None
