from contextlib import asynccontextmanager, contextmanager
from typing import (
    AsyncGenerator,
    AsyncIterator,
    Generator,
    Type,
    TypeVar,
    overload,
)

from httpx import AsyncClient, Client
from nuclia_models.agent.api import SessionData
from nuclia_models.agent.interaction import (
    AnswerOperation,
    AragAnswer,
    InteractionOperation,
    InteractionRequest,
    UserToAgentInteraction,
)
from nuclia_models.common.formats import TextFormat
from nucliadb_models.resource import Resource, ResourceList
from nucliadb_models.writer import ResourceCreated
from pydantic import BaseModel
from websockets.asyncio.client import ClientConnection as AsyncClientConnection
from websockets.asyncio.client import connect as async_connect
from websockets.sync.client import connect

from nuclia import REGIONAL
from nuclia.exceptions import RaoAPIException
from nuclia.lib.utils import (
    USER_AGENT,
    build_httpx_async_client,
    build_httpx_client,
)

ConvertType = TypeVar("ConvertType", bound=BaseModel)


class BaseAgentClient:
    """Base class containing common logic for Agent clients."""

    region: str
    agent_id: str
    account_id: str
    headers: dict[str, str]
    user_token: str | None
    url: str
    ws_url: str

    def __init__(
        self,
        region: str,
        agent_id: str,
        account_id: str,
        api_key: str | None = None,
        user_token: str | None = None,
        headers: dict[str, str] | None = None,
    ):
        self.region = region
        self.agent_id = agent_id
        self.account_id = account_id
        self.user_token = user_token

        # Build URL from region
        if "http" in region:
            self.url = region.strip("/")
        else:
            self.url = REGIONAL.format(region=region).strip("/")

        # Build WebSocket URL
        self.ws_url = self.url.replace("https://", "wss://")

        # Build headers
        self.headers = {"User-Agent": USER_AGENT}
        if api_key is not None:
            self.headers["X-NUCLIA-SERVICEACCOUNT"] = f"Bearer {api_key}"
        elif user_token is not None:
            self.headers["Authorization"] = f"Bearer {user_token}"
        if headers is not None:
            self.headers = self.headers | headers


class AgentClient(BaseAgentClient):
    """Synchronous Agent client."""

    http_client: Client

    def __init__(
        self,
        region: str,
        agent_id: str,
        account_id: str,
        api_key: str | None = None,
        user_token: str | None = None,
        headers: dict[str, str] | None = None,
    ):
        super().__init__(region, agent_id, account_id, api_key, user_token, headers)
        self.http_client = build_httpx_client(headers=self.headers, base_url=self.url)

    @overload
    def _request(
        self,
        method: str,
        url: str,
        output: None = None,
        payload: dict | BaseModel | None = None,
        params: dict | None = None,
        extra_headers: dict[str, str] | None = None,
        timeout: int = 60,
    ) -> dict: ...

    @overload
    def _request(
        self,
        method: str,
        url: str,
        output: Type[ConvertType],
        payload: dict | BaseModel | None = None,
        params: dict | None = None,
        extra_headers: dict[str, str] | None = None,
        timeout: int = 60,
    ) -> ConvertType: ...

    def _request(
        self,
        method: str,
        url: str,
        output: Type[ConvertType] | None = None,
        payload: dict | BaseModel | None = None,
        params: dict | None = None,
        extra_headers: dict[str, str] | None = None,
        timeout: int = 60,
    ) -> ConvertType | dict:
        if isinstance(payload, BaseModel):
            payload = payload.model_dump(mode="json")
        resp = self.http_client.request(
            method,
            url,
            json=payload,
            timeout=timeout,
            headers=extra_headers,
            params=params,
        )
        if resp.status_code != 200 and resp.status_code != 201:
            raise RaoAPIException(code=resp.status_code, detail=resp.content.decode())
        if output:
            try:
                data = output.model_validate(resp.json())
            except Exception:
                data = output.model_validate(resp.content)
        else:
            data = resp.json()
        return data

    def new_session(self, name: str) -> str:
        return self.create_session(
            SessionData(
                slug=name.replace(" ", "-").lower(),
                name=name,
                summary="",
                data="",
                format=TextFormat.PLAIN,
            )
        ).uuid

    def create_session(self, session_data: SessionData) -> ResourceCreated:
        return self._request(
            "POST",
            f"/api/v1/agent/{self.agent_id}/sessions",
            output=ResourceCreated,
            payload=session_data,
        )

    def delete_session(self, session_uuid: str) -> None:
        self._request(
            "DELETE", f"/api/v1/kb/{self.agent_id}/agent/session/{session_uuid}"
        )

    def get_sessions(self, page: int = 0, page_size=20) -> ResourceList:
        return self._request(
            "GET",
            f"/api/v1/kb/{self.agent_id}/agent/sessions",
            output=ResourceList,
            params={"page": page, "page_size": page_size},
        )

    def get_session(self, session_uuid: str) -> Resource:
        return self._request(
            "GET",
            f"/api/v1/kb/{self.agent_id}/agent/session/{session_uuid}",
            output=Resource,
        )

    def get_ephemeral_token(self, session_uuid: str) -> str:
        resp = self._request(
            "POST",
            f"/api/v1/account/{self.account_id}/kb/{self.agent_id}/ephemeral_tokens",
            payload={"agent_session": session_uuid},
        )
        return resp["token"]

    @contextmanager
    def websocket(self, session_uuid: str):
        eph_token = self.get_ephemeral_token(session_uuid)
        with connect(
            f"{self.ws_url}/api/v1/agent/{self.agent_id}/session/{session_uuid}/ws?eph-token={eph_token}"
        ) as websocket:
            yield websocket

    def interact(
        self, session_uuid: str, question: str
    ) -> Generator[AragAnswer, str | None, None]:
        message = InteractionRequest(
            question=question, headers={}, operation=InteractionOperation.QUESTION
        ).model_dump_json()
        with self.websocket(session_uuid) as websocket:
            websocket.send(message)
            user_response = None
            for data in websocket:
                response = AragAnswer.model_validate_json(data)

                # If we need a user response, yield the response and wait for input
                if response.operation == AnswerOperation.AGENT_REQUEST:
                    user_response = yield response
                    if user_response and response.agent_request:
                        # Send user response back to agent
                        user_msg = UserToAgentInteraction(
                            request_id=response.agent_request,
                            response=user_response,
                        ).model_dump_json()
                        websocket.send(user_msg)
                else:
                    yield response


class AsyncAgentClient(BaseAgentClient):
    """Asynchronous Agent client."""

    http_client: AsyncClient

    def __init__(
        self,
        region: str,
        agent_id: str,
        account_id: str,
        api_key: str | None = None,
        user_token: str | None = None,
        headers: dict[str, str] | None = None,
    ):
        super().__init__(region, agent_id, account_id, api_key, user_token, headers)
        self.http_client = build_httpx_async_client(
            headers=self.headers, base_url=self.url
        )

    @overload
    async def _request(
        self,
        method: str,
        url: str,
        output: None = None,
        payload: dict | BaseModel | None = None,
        params: dict | None = None,
        extra_headers: dict[str, str] | None = None,
        timeout: int = 60,
    ) -> dict: ...

    @overload
    async def _request(
        self,
        method: str,
        url: str,
        output: Type[ConvertType],
        payload: dict | BaseModel | None = None,
        params: dict | None = None,
        extra_headers: dict[str, str] | None = None,
        timeout: int = 60,
    ) -> ConvertType: ...

    async def _request(
        self,
        method: str,
        url: str,
        output: Type[ConvertType] | None = None,
        payload: dict | BaseModel | None = None,
        params: dict | None = None,
        extra_headers: dict[str, str] | None = None,
        timeout: int = 60,
    ) -> ConvertType | dict:
        if isinstance(payload, BaseModel):
            payload = payload.model_dump(mode="json")
        resp = await self.http_client.request(
            method,
            url,
            json=payload,
            timeout=timeout,
            headers=extra_headers,
            params=params,
        )
        if resp.status_code != 200 and resp.status_code != 201:
            raise RaoAPIException(code=resp.status_code, detail=resp.content.decode())
        if output:
            try:
                data = output.model_validate(resp.json())
            except Exception:
                data = output.model_validate(resp.content)
        else:
            data = resp.json()
        return data

    async def new_session(self, name: str) -> str:
        return (
            await self.create_session(
                SessionData(
                    slug=name.replace(" ", "-").lower(),
                    name=name,
                    summary="",
                    data="",
                    format=TextFormat.PLAIN,
                )
            )
        ).uuid

    async def create_session(self, session_data: SessionData) -> ResourceCreated:
        return await self._request(
            "POST",
            f"/api/v1/agent/{self.agent_id}/sessions",
            output=ResourceCreated,
            payload=session_data,
        )

    async def delete_session(self, session_uuid: str) -> None:
        await self._request(
            "DELETE", f"/api/v1/kb/{self.agent_id}/agent/session/{session_uuid}"
        )

    async def get_sessions(self, page: int = 0, page_size=20) -> ResourceList:
        return await self._request(
            "GET",
            f"/api/v1/kb/{self.agent_id}/agent/sessions",
            output=ResourceList,
            params={"page": page, "page_size": page_size},
        )

    async def get_session(self, session_uuid: str) -> Resource:
        return await self._request(
            "GET",
            f"/api/v1/kb/{self.agent_id}/agent/session/{session_uuid}",
            output=Resource,
        )

    async def get_ephemeral_token(self, session_uuid: str) -> str:
        resp = await self._request(
            "POST",
            f"/api/v1/account/{self.account_id}/kb/{self.agent_id}/ephemeral_tokens",
            payload={"agent_session": session_uuid},
        )
        return resp["token"]

    @asynccontextmanager
    async def websocket(
        self, session_uuid: str
    ) -> AsyncGenerator[AsyncClientConnection, None]:
        eph_token = await self.get_ephemeral_token(session_uuid)
        async with async_connect(
            f"{self.ws_url}/api/v1/agent/{self.agent_id}/session/{session_uuid}/ws?eph-token={eph_token}",
        ) as websocket:
            yield websocket

    async def interact(
        self, session_uuid: str, question: str
    ) -> AsyncIterator[AragAnswer]:
        message = InteractionRequest(
            question=question, headers={}, operation=InteractionOperation.QUESTION
        ).model_dump_json()
        async with self.websocket(session_uuid) as websocket:
            await websocket.send(message)
            async for data in websocket:
                response = AragAnswer.model_validate_json(data)
                yield response
