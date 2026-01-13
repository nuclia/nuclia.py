import pytest

from nuclia.sdk.auth import AsyncNucliaAuth, NucliaAuth
from nuclia.tests.fixtures import TESTING_KB, TESTING_KBID


def test_auth_user(testing_user: str):
    na = NucliaAuth()
    assert na._validate_user_token(testing_user)


def test_auth_kb(testing_kb: str):
    na = NucliaAuth()
    kbobj = na.validate_kb(TESTING_KB, testing_kb)
    assert kbobj
    assert kbobj.uuid
    assert kbobj.config
    assert kbobj.config.title


def test_auth_nua(testing_nua: str):
    na = NucliaAuth()
    client, account_type, account, region = na.validate_nua(testing_nua)
    assert client
    assert account_type
    assert account


def test_auth_pat(testing_config):
    na = NucliaAuth()
    token = na.create_personal_token(description="sdk test token", days=1, login=False)
    assert token
    tokens = na.list_personal_tokens()
    assert len([t.id for t in tokens if t.id == token.id]) == 1
    na.delete_personal_token(token_id=token.id)
    tokens = na.list_personal_tokens()
    assert len([t.id for t in tokens if t.id == token.id]) == 0


def test_auth_ephemeral_token(testing_config, testing_kb):
    na = NucliaAuth()
    token = na.create_ephemeral_token(kbid=TESTING_KBID)

    assert token
    assert token.token is not None

    token = na.create_ephemeral_token(kbid=TESTING_KBID, ttl=3600)

    assert token
    assert token.token is not None


def test_get_account_from_service_token(testing_kb: str):
    na = NucliaAuth()
    region = "europe-1"

    account_id, kb_id, role = na.get_account_from_service_token(region, testing_kb)

    assert account_id is not None
    assert kb_id is not None
    assert role is not None
    assert kb_id == TESTING_KBID


@pytest.mark.asyncio
async def test_get_account_from_service_token_async(testing_kb: str):
    na = AsyncNucliaAuth()
    region = "europe-1"

    account_id, kb_id, role = await na.get_account_from_service_token(
        region, testing_kb
    )

    assert account_id is not None
    assert kb_id is not None
    assert role is not None
    assert kb_id == TESTING_KBID


@pytest.mark.asyncio
async def test_auth_ephemeral_token_async(testing_config, testing_kb):
    na = AsyncNucliaAuth()
    token = await na.create_ephemeral_token(kbid=TESTING_KBID)

    assert token
    assert token.token is not None

    token = await na.create_ephemeral_token(kbid=TESTING_KBID, ttl=3600)

    assert token
    assert token.token is not None


@pytest.mark.asyncio
async def test_async_auth_user(testing_user: str):
    na = AsyncNucliaAuth()
    assert await na._validate_user_token(testing_user)


@pytest.mark.asyncio
async def test_async_auth_kb(testing_kb: str):
    na = AsyncNucliaAuth()
    kbobj = await na.validate_kb(TESTING_KB, testing_kb)
    assert kbobj
    assert kbobj.uuid
    assert kbobj.config
    assert kbobj.config.title


@pytest.mark.asyncio
async def test_async_auth_nua(testing_nua: str):
    na = AsyncNucliaAuth()
    client, account_type, account, region = await na.validate_nua(testing_nua)
    assert client
    assert account_type
    assert account


@pytest.mark.asyncio
async def test_async_auth_kb_url(testing_kb: str):
    na = AsyncNucliaAuth()
    kb_uuid = await na.kb(TESTING_KB, testing_kb)
    assert kb_uuid == TESTING_KBID


@pytest.mark.asyncio
async def test_async_auth_nua_token(testing_nua: str):
    na = AsyncNucliaAuth()
    client_id = await na.nua(testing_nua)
    assert client_id is not None


@pytest.mark.asyncio
async def test_async_auth_accounts(testing_config):
    na = AsyncNucliaAuth()
    accounts = await na.accounts()
    assert len(accounts) > 0
    assert accounts[0].id
    assert accounts[0].slug


@pytest.mark.asyncio
async def test_async_auth_zones(testing_config):
    na = AsyncNucliaAuth()
    zones = await na.zones()
    assert len(zones) > 0
    assert zones[0].slug


@pytest.mark.asyncio
async def test_async_auth_kbs(testing_config):
    na = AsyncNucliaAuth()
    accounts = await na.accounts()
    assert len(accounts) > 0
    kbs = await na.kbs(accounts[0].id)
    # Should return a list (may be empty depending on account)
    assert isinstance(kbs, list)


@pytest.mark.asyncio
async def test_async_auth_agents(testing_config):
    na = AsyncNucliaAuth()
    accounts = await na.accounts()
    assert len(accounts) > 0
    agents = await na.agents(accounts[0].id)
    # Should return a list (may be empty depending on account)
    assert isinstance(agents, list)


def test_auth_agent_url(testing_agent: str):
    from nuclia.tests.fixtures import (
        TESTING_ACCOUNT_ID,
        TESTING_AGENT_ID,
        TESTING_AGENT_REGION,
    )

    na = NucliaAuth()
    agent_uuid = na.agent(
        region=TESTING_AGENT_REGION,
        account_id=TESTING_ACCOUNT_ID,
        agent_id=TESTING_AGENT_ID,
        token=testing_agent,
    )
    assert agent_uuid == TESTING_AGENT_ID


@pytest.mark.asyncio
async def test_async_auth_agent_url(testing_agent: str):
    from nuclia.tests.fixtures import (
        TESTING_ACCOUNT_ID,
        TESTING_AGENT_ID,
        TESTING_AGENT_REGION,
    )

    na = AsyncNucliaAuth()
    agent_uuid = await na.agent(
        region=TESTING_AGENT_REGION,
        account_id=TESTING_ACCOUNT_ID,
        agent_id=TESTING_AGENT_ID,
        token=testing_agent,
    )
    assert agent_uuid == TESTING_AGENT_ID
