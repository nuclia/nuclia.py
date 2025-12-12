import pytest

from nuclia.sdk.agents import AsyncNucliaAgents, NucliaAgents
from nuclia.tests.fixtures import IS_PROD, TESTING_ACCOUNT_SLUG, TESTING_AGENT_ID


def test_list_agents(testing_config):
    agents = NucliaAgents()
    all = agents.list()
    if not IS_PROD and TESTING_AGENT_ID:
        assert TESTING_AGENT_ID in [agent.id for agent in all]


@pytest.mark.asyncio
async def test_async_list_agents(testing_config):
    agents = AsyncNucliaAgents()
    all = await agents.list()
    if not IS_PROD and TESTING_AGENT_ID:
        assert TESTING_AGENT_ID in [agent.id for agent in all]


def test_get_agent(testing_config):
    if not TESTING_AGENT_ID:
        # Skip if no agent configured
        assert True
        return
    agents = NucliaAgents()
    agent = agents.get(
        account=TESTING_ACCOUNT_SLUG, id=TESTING_AGENT_ID, zone="europe-1"
    )
    assert agent is not None
    assert agent["id"] == TESTING_AGENT_ID


@pytest.mark.asyncio
async def test_async_get_agent(testing_config):
    if not TESTING_AGENT_ID:
        # Skip if no agent configured
        assert True
        return
    agents = AsyncNucliaAgents()
    agent = await agents.get(
        account=TESTING_ACCOUNT_SLUG, id=TESTING_AGENT_ID, zone="europe-1"
    )
    assert agent is not None
    assert agent["id"] == TESTING_AGENT_ID
