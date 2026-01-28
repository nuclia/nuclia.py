import asyncio
from typing import Type, Union
from uuid import uuid4

import pytest

from nuclia.sdk.agent_sessions import AsyncNucliaAgentSessions, NucliaAgentSessions
from nuclia.tests.utils import maybe_await


@pytest.mark.parametrize(
    "agent_sessions_klass",
    [NucliaAgentSessions, AsyncNucliaAgentSessions],
)
async def test_sessions(
    testing_config,
    use_agent,
    agent_sessions_klass: Type[Union[NucliaAgentSessions, AsyncNucliaAgentSessions]],
):
    n_agent_sess = agent_sessions_klass()

    session_name = f"nuclia-py-test-{uuid4().hex}"
    # Create session
    uuid = await maybe_await(n_agent_sess.new(session_name))

    # Get session
    session = await maybe_await(n_agent_sess.get(uuid))
    assert session.title == session_name

    # List sessions, scan all pages since the endpoint does not support sorting by creation date
    last = False
    found = False
    p = 0
    while not last:
        sessions = await maybe_await(n_agent_sess.list(page_size=100, page=p))
        last = sessions.pagination.last
        p += 1
        found = any(s.id == uuid for s in sessions.resources)
        if found:
            break
    assert found

    # Delete session
    await maybe_await(n_agent_sess.delete(uuid))
    # Wait a bit for deletion to propagate
    await asyncio.sleep(1)
    with pytest.raises(Exception):
        await maybe_await(n_agent_sess.get(uuid))
