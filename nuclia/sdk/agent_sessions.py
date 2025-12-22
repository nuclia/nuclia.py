from nucliadb_models.resource import Resource, ResourceList

from nuclia.decorators import agent
from nuclia.lib.agent import AgentClient, AsyncAgentClient


class NucliaAgentSessions:
    @agent
    def new(self, name: str, **kwargs) -> str:
        ac: AgentClient = kwargs["ac"]
        return ac.new_session(name)

    @agent
    def delete(self, session_uuid: str, **kwargs):
        ac: AgentClient = kwargs["ac"]
        return ac.delete_session(session_uuid)

    @agent
    def list(self, **kwargs) -> ResourceList:
        ac: AgentClient = kwargs["ac"]
        return ac.get_sessions()

    @agent
    def get(self, session_uuid: str, **kwargs) -> Resource:
        ac: AgentClient = kwargs["ac"]
        return ac.get_session(session_uuid)


class AsyncNucliaAgentSessions:
    @agent
    async def new(self, name: str, **kwargs) -> str:
        ac: AsyncAgentClient = kwargs["ac"]
        return await ac.new_session(name)

    @agent
    async def delete(self, session_uuid: str, **kwargs):
        ac: AsyncAgentClient = kwargs["ac"]
        return await ac.delete_session(session_uuid)

    @agent
    async def list(self, page: int = 0, page_size: int = 20, **kwargs) -> ResourceList:
        ac: AsyncAgentClient = kwargs["ac"]
        return await ac.get_sessions(page=page, page_size=page_size)

    @agent
    async def get(self, session_uuid: str, **kwargs) -> Resource:
        ac: AsyncAgentClient = kwargs["ac"]
        return await ac.get_session(session_uuid)
