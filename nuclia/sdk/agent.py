from typing import AsyncIterator, Iterator, Optional

from nuclia_models.agent.interaction import AragAnswer

from nuclia.data import get_auth
from nuclia.decorators import agent
from nuclia.lib.agent import AgentClient, AsyncAgentClient
from nuclia.sdk.agent_cli import NucliaAgentCLI
from nuclia.sdk.agent_sessions import AsyncNucliaAgentSessions, NucliaAgentSessions
from nuclia.sdk.auth import NucliaAuth


class NucliaAgent:
    session: NucliaAgentSessions
    cli: NucliaAgentCLI

    @property
    def _auth(self) -> NucliaAuth:
        auth = get_auth()
        return auth

    def __init__(self) -> None:
        self.session = NucliaAgentSessions()
        self.cli = NucliaAgentCLI()

    @agent
    def interact(
        self,
        question: str,
        session_uuid: str = "ephemeral",
        headers: Optional[dict[str, str]] = None,
        **kwargs,
    ) -> Iterator[AragAnswer]:
        ac: AgentClient = kwargs["ac"]
        for response in ac.interact(session_uuid, question, headers=headers):
            yield response


class AsyncNucliaAgent:
    session: "AsyncNucliaAgentSessions"

    @property
    def _auth(self) -> NucliaAuth:
        auth = get_auth()
        return auth

    def __init__(self) -> None:
        self.session = AsyncNucliaAgentSessions()

    @agent
    async def interact(
        self,
        question: str,
        session_uuid: str = "ephemeral",
        headers: Optional[dict[str, str]] = None,
        **kwargs,
    ) -> AsyncIterator[AragAnswer]:
        ac: AsyncAgentClient = kwargs["ac"]
        async for response in ac.interact(session_uuid, question, headers=headers):
            yield response
