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
    agent_sessions_klass: Type[Union[NucliaAgentSessions, AsyncNucliaAgentSessions]],
):
    n_agent_sess = agent_sessions_klass()

    session_name = f"nuclia-py-test-{uuid4().hex}"
    # Create session
    uuid = await maybe_await(n_agent_sess.new(session_name))

    # Get session
    session = await maybe_await(n_agent_sess.get(uuid))
    assert session.title == session_name

    # List sessions
    sessions = await maybe_await(n_agent_sess.list())
    assert any(s.id == uuid for s in sessions.resources)

    # Delete session
    await maybe_await(n_agent_sess.delete(uuid))
    with pytest.raises(Exception):
        await maybe_await(n_agent_sess.get(uuid))
