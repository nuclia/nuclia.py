import pytest

from nuclia.sdk.agents import AsyncNucliaAgents, NucliaAgents
from nuclia.tests.fixtures import (
    TESTING_ACCOUNT_SLUG,
    TESTING_AGENT_ID,
    TESTING_AGENT_NO_MEM_ID,
)


def test_list_agents(testing_config):
    agents = NucliaAgents()
    all = agents.list()
    agent_ids = [agent.id for agent in all]
    assert TESTING_AGENT_ID in agent_ids
    assert TESTING_AGENT_NO_MEM_ID in agent_ids


@pytest.mark.asyncio
async def test_async_list_agents(testing_config):
    agents = AsyncNucliaAgents()
    all = await agents.list()
    agent_ids = [agent.id for agent in all]
    assert TESTING_AGENT_ID in agent_ids
    assert TESTING_AGENT_NO_MEM_ID in agent_ids


@pytest.mark.parametrize("agent_id", [TESTING_AGENT_ID, TESTING_AGENT_NO_MEM_ID])
def test_get_agent(testing_config, agent_id):
    agents = NucliaAgents()
    agent = agents.get(account=TESTING_ACCOUNT_SLUG, id=agent_id, zone="europe-1")
    assert agent is not None
    assert agent["id"] == agent_id


@pytest.mark.asyncio
@pytest.mark.parametrize("agent_id", [TESTING_AGENT_ID, TESTING_AGENT_NO_MEM_ID])
async def test_async_get_agent(testing_config, agent_id):
    agents = AsyncNucliaAgents()
    agent = await agents.get(account=TESTING_ACCOUNT_SLUG, id=agent_id, zone="europe-1")
    assert agent is not None
    assert agent["id"] == agent_id
