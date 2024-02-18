import base64
from time import sleep
from typing import Any, Dict, List, Optional, Type, TypeVar

import aiofiles
from httpx import AsyncClient, Client
from nucliadb_protos.writer_pb2 import BrokerMessage
from pydantic import BaseModel

from nuclia import REGIONAL
from nuclia.exceptions import NuaAPIException
from nuclia.lib.nua_responses import (
    ChatModel,
    ChatResponse,
    ConfigSchema,
    Empty,
    LearningConfigurationCreation,
    LearningConfigurationUpdate,
    LinkUpload,
    ProcessRequestStatus,
    ProcessRequestStatusResults,
    PushPayload,
    PushResponseV2,
    RestrictedIDString,
    Sentence,
    Source,
    StoredLearningConfiguration,
    SummarizedModel,
    SummarizeModel,
    SummarizeResource,
    Tokens,
    UserPrompt,
)

SENTENCE_PREDICT = "/api/v1/predict/sentence"
CHAT_PREDICT = "/api/v1/predict/chat"
SUMMARIZE_PREDICT = "/api/v1/predict/summarize"
TOKENS_PREDICT = "/api/v1/predict/tokens"
UPLOAD_PROCESS = "/api/v1/processing/upload"
STATUS_PROCESS = "/api/v2/processing/status"
PUSH_PROCESS = "/api/v2/processing/push"
SCHEMA = "/api/v1/learning/configuration/schema"
SCHEMA_KBID = "/api/v1/schema"
CONFIG = "/api/v1/config"

ConvertType = TypeVar("ConvertType", bound=BaseModel)


class NuaClient:
    def __init__(self, region: str, account: str, token: str):
        self.region = region
        self.account = account
        self.token = token
        if "http" in region:
            self.url = region.strip("/")
        else:
            self.url = REGIONAL.format(region=region).strip("/")
        self.headers = {"X-STF-NUAKEY": f"Bearer {token}"}
        self.client = Client(headers=self.headers, base_url=self.url)

    def _request(
        self,
        method: str,
        url: str,
        output: Type[ConvertType],
        json: Optional[Dict[Any, Any]] = None,
        timeout: int = 60,
    ) -> ConvertType:
        resp = self.client.request(method, url, json=json, timeout=timeout)
        if resp.status_code != 200:
            raise NuaAPIException(code=resp.status_code, detail=resp.content.decode())

        try:
            data = output.parse_obj(resp.json())
        except Exception:
            data = output.parse_raw(resp.content)
        return data

    def add_config_predict(self, kbid: str, config: LearningConfigurationCreation):
        endpoint = f"{self.url}{CONFIG}/{kbid}"
        self._request(
            "POST", endpoint, json=config.dict(exclude_none=True), output=Empty
        )

    def del_config_predict(self, kbid: str):
        endpoint = f"{self.url}{CONFIG}/{kbid}"
        self._request("DELETE", endpoint, output=Empty)

    def update_config_predict(self, kbid: str, config: LearningConfigurationUpdate):
        endpoint = f"{self.url}{CONFIG}/{kbid}"
        self._request(
            "POST", endpoint, json=config.dict(exclude_none=True), output=Empty
        )

    def schema_predict(self, kbid: Optional[str] = None) -> ConfigSchema:
        endpoint = f"{self.url}{SCHEMA}"
        if kbid is not None:
            endpoint = f"{self.url}{SCHEMA_KBID}/{kbid}"
        return self._request("GET", endpoint, output=ConfigSchema)

    def config_predict(self, kbid: str) -> StoredLearningConfiguration:
        endpoint = f"{self.url}{CONFIG}"
        if kbid is not None:
            endpoint = f"{self.url}{CONFIG}/{kbid}"
        return self._request("GET", endpoint, output=StoredLearningConfiguration)

    def sentence_predict(self, text: str, model: Optional[str] = None) -> Sentence:
        endpoint = f"{self.url}{SENTENCE_PREDICT}?text={text}"
        if model:
            endpoint += f"&model={model}"
        return self._request("GET", endpoint, output=Sentence)

    def tokens_predict(self, text: str, model: Optional[str] = None) -> Tokens:
        endpoint = f"{self.url}{TOKENS_PREDICT}?text={text}"
        if model:
            endpoint += f"&model={model}"
        return self._request("GET", endpoint, output=Tokens)

    def generate_predict(
        self, text: str, model: Optional[str] = None, timeout: int = 300
    ) -> ChatResponse:
        endpoint = f"{self.url}{CHAT_PREDICT}"
        if model:
            endpoint += f"?model={model}"

        body = ChatModel(
            question="",
            retrieval=False,
            user_id="Nuclia PY CLI",
            user_prompt=UserPrompt(prompt=text),
        )
        return self._request(
            "POST", endpoint, json=body.dict(), output=ChatResponse, timeout=timeout
        )

    def summarize(
        self, documents: Dict[str, str], model: Optional[str] = None, timeout: int = 300
    ) -> SummarizedModel:
        endpoint = f"{self.url}{SUMMARIZE_PREDICT}"
        if model:
            endpoint += f"?model={model}"

        body = SummarizeModel(
            resources={
                key: SummarizeResource(fields={"field": document})
                for key, document in documents.items()
            }
        )
        return self._request(
            "POST", endpoint, json=body.dict(), output=SummarizedModel, timeout=timeout
        )

    def generate_retrieval(
        self,
        question: str,
        context: List[str],
        model: Optional[str] = None,
    ) -> ChatResponse:
        endpoint = f"{self.url}{CHAT_PREDICT}"
        if model:
            endpoint += f"?model={model}"
        body = ChatModel(
            question=question,
            retrieval=True,
            user_id="Nuclia PY CLI",
            query_context=context,
        )
        return self._request("POST", endpoint, json=body.dict(), output=ChatResponse)

    def process_file(self, path: str, kbid: str = "default") -> PushResponseV2:
        filename = path.split("/")[-1]
        upload_endpoint = f"{self.url}{UPLOAD_PROCESS}"

        headers = self.headers.copy()
        headers["X-FILENAME"] = base64.b64encode(filename.encode()).decode()
        with open(path, "rb") as file_to_upload:
            data = file_to_upload.read()

        resp = self.client.post(upload_endpoint, content=data, headers=headers)

        payload = PushPayload(
            uuid=None, source=Source.HTTP, kbid=RestrictedIDString(kbid)
        )

        payload.filefield[filename] = resp.content.decode()
        process_endpoint = f"{self.url}{PUSH_PROCESS}"
        return self._request(
            "POST", process_endpoint, json=payload.dict(), output=PushResponseV2
        )

    def process_link(
        self,
        url: str,
        kbid: Optional[str] = None,
        headers: Dict[str, str] = {},
        cookies: Dict[str, str] = {},
        localstorage: Dict[str, str] = {},
    ) -> PushResponseV2:
        payload = PushPayload(
            uuid=None, source=Source.HTTP, kbid=RestrictedIDString(kbid)
        )

        payload.linkfield["link"] = LinkUpload(
            link=url, headers=headers, cookies=cookies, localstorage=localstorage
        )
        process_endpoint = f"{self.url}{PUSH_PROCESS}"
        return self._request(
            "POST", process_endpoint, json=payload.dict(), output=PushResponseV2
        )

    def wait_for_processing(
        self, response: PushResponseV2, timeout: int = 30
    ) -> Optional[BrokerMessage]:
        resp = self.processing_id_status(response.processing_id)
        count = timeout
        while resp.completed is False and resp.failed is False and count > 0:
            resp = self.processing_id_status(response.processing_id)
            sleep(3)
            count -= 1

        bm = None
        if resp.response:
            bm = BrokerMessage()
            bm.ParseFromString(base64.b64decode(resp.response))

        return bm

    def processing_status(self) -> ProcessRequestStatusResults:
        activity_endpoint = f"{self.url}{STATUS_PROCESS}"
        return self._request("GET", activity_endpoint, ProcessRequestStatusResults)

    def processing_id_status(self, process_id: str) -> ProcessRequestStatus:
        activity_endpoint = f"{self.url}{STATUS_PROCESS}/{process_id}"
        return self._request("GET", activity_endpoint, ProcessRequestStatus)


class AsyncNuaClient:
    def __init__(self, region: str, account: str, token: str):
        self.region = region
        self.account = account
        self.token = token
        if "http" in region:
            self.url = region.strip("/")
        else:
            self.url = REGIONAL.format(region=region).strip("/")
        self.headers = {"X-STF-NUAKEY": f"Bearer {token}"}
        self.client = AsyncClient(headers=self.headers, base_url=self.url)

    async def _request(
        self,
        method: str,
        url: str,
        output: Type[ConvertType],
        json: Optional[Dict[Any, Any]] = None,
        timeout: int = 60,
    ) -> ConvertType:
        resp = await self.client.request(method, url, json=json, timeout=timeout)
        if resp.status_code != 200:
            raise NuaAPIException(code=resp.status_code, detail=resp.content.decode())

        try:
            data = output.parse_obj(resp.json())
        except Exception:
            data = output()
        return data

    async def add_config_predict(
        self, kbid: str, config: LearningConfigurationCreation
    ):
        endpoint = f"{CONFIG}/{kbid}"
        await self._request(
            "GET", endpoint, json=config.dict(exclude_none=True), output=Empty
        )

    async def del_config_predict(self, kbid: str):
        endpoint = f"{self.url}{CONFIG}/{kbid}"
        await self._request("DELETE", endpoint, output=Empty)

    async def update_config_predict(
        self, kbid: str, config: LearningConfigurationUpdate
    ):
        endpoint = f"{CONFIG}/{kbid}"
        await self._request(
            "POST", endpoint, json=config.dict(exclude_none=True), output=Empty
        )

    async def schema_predict(self, kbid: Optional[str] = None) -> ConfigSchema:
        endpoint = f"{SCHEMA}"
        if kbid is not None:
            endpoint = f"{SCHEMA_KBID}/{kbid}"
        return await self._request("GET", endpoint, output=ConfigSchema)  # type: ignore

    async def config_predict(
        self, kbid: Optional[str] = None
    ) -> StoredLearningConfiguration:
        endpoint = f"{self.url}{CONFIG}"
        if kbid is not None:
            endpoint = f"{self.url}{CONFIG}/{kbid}"
        return await self._request("GET", endpoint, output=StoredLearningConfiguration)

    async def sentence_predict(
        self, text: str, model: Optional[str] = None
    ) -> Sentence:
        endpoint = f"{self.url}{SENTENCE_PREDICT}?text={text}"
        if model:
            endpoint += f"&model={model}"
        return await self._request("GET", endpoint, output=Sentence)

    async def tokens_predict(self, text: str, model: Optional[str] = None) -> Tokens:
        endpoint = f"{self.url}{TOKENS_PREDICT}?text={text}"
        if model:
            endpoint += f"&model={model}"
        return await self._request("GET", endpoint, output=Tokens)

    async def generate_predict(
        self, text: str, model: Optional[str] = None, timeout: int = 300
    ) -> ChatResponse:
        endpoint = f"{self.url}{CHAT_PREDICT}"
        if model:
            endpoint += f"?model={model}"

        body = ChatModel(
            question="",
            retrieval=False,
            user_id="Nuclia PY CLI",
            user_prompt=UserPrompt(prompt=text),
        )

        return await self._request(
            "POST", endpoint, json=body.dict(), output=ChatResponse, timeout=timeout
        )

    async def summarize(
        self, documents: Dict[str, str], model: Optional[str] = None, timeout: int = 300
    ) -> SummarizedModel:
        endpoint = f"{self.url}{SUMMARIZE_PREDICT}"
        if model:
            endpoint += f"?model={model}"

        body = SummarizeModel(
            resources={
                key: SummarizeResource(fields={"field": document})
                for key, document in documents.items()
            }
        )
        return await self._request(
            "POST", endpoint, json=body.dict(), output=SummarizedModel, timeout=timeout
        )

    async def generate_retrieval(
        self,
        question: str,
        context: List[str],
        model: Optional[str] = None,
    ) -> ChatResponse:
        endpoint = f"{self.url}{CHAT_PREDICT}"
        if model:
            endpoint += f"?model={model}"
        body = ChatModel(
            question=question,
            retrieval=True,
            user_id="Nuclia PY CLI",
            query_context=context,
        )
        return await self._request(
            "POST", endpoint, json=body.dict(), output=ChatResponse
        )

    async def process_link(
        self,
        url: str,
        kbid: Optional[str] = None,
        headers: Dict[str, str] = {},
        cookies: Dict[str, str] = {},
        localstorage: Dict[str, str] = {},
    ) -> PushResponseV2:
        payload = PushPayload(
            uuid=None, source=Source.HTTP, kbid=RestrictedIDString(kbid)
        )

        payload.linkfield["link"] = LinkUpload(
            link=url, headers=headers, cookies=cookies, localstorage=localstorage
        )
        process_endpoint = f"{self.url}{PUSH_PROCESS}"
        return await self._request(
            "POST", process_endpoint, json=payload.dict(), output=PushResponseV2
        )

    async def process_file(
        self, path: str, kbid: Optional[str] = None
    ) -> PushResponseV2:
        filename = path.split("/")[-1]
        upload_endpoint = f"{self.url}{UPLOAD_PROCESS}"

        headers = self.headers.copy()
        headers["X-FILENAME"] = base64.b64encode(filename.encode()).decode()
        async with aiofiles.open(path, "rb") as file_to_upload:
            data = await file_to_upload.read()

        resp = await self.client.post(upload_endpoint, content=data, headers=headers)

        payload = PushPayload(
            uuid=None, source=Source.HTTP, kbid=RestrictedIDString(kbid)
        )

        payload.filefield[filename] = resp.content.decode()
        process_endpoint = f"{self.url}{PUSH_PROCESS}"
        return await self._request(
            "POST", process_endpoint, json=payload.dict(), output=PushResponseV2
        )

    async def wait_for_processing(
        self, response: PushResponseV2, timeout: int = 30
    ) -> Optional[BrokerMessage]:
        status = await self.processing_id_status(response.processing_id)
        count = timeout
        while status.completed is False and status.failed is False and count > 0:
            status = await self.processing_id_status(response.processing_id)
            sleep(3)
            count -= 1

        bm = None
        if status.response:
            bm = BrokerMessage()
            bm.ParseFromString(base64.b64decode(status.response))

        return bm

    async def processing_status(self) -> ProcessRequestStatusResults:
        activity_endpoint = f"{self.url}{STATUS_PROCESS}"
        return await self._request(
            "GET", activity_endpoint, output=ProcessRequestStatusResults
        )

    async def processing_id_status(self, process_id: str) -> ProcessRequestStatus:
        activity_endpoint = f"{self.url}{STATUS_PROCESS}/{process_id}"
        return await self._request(
            "GET", activity_endpoint, output=ProcessRequestStatus
        )
