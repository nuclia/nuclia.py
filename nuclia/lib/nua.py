import base64
from enum import Enum
from time import sleep
from typing import (
    Any,
    AsyncIterator,
    Iterator,
    Optional,
    Type,
    TypeVar,
    Union,
)

import aiofiles
from deprecated import deprecated
from httpx import AsyncClient, Client
from nucliadb_protos.writer_pb2 import BrokerMessage
from pydantic import BaseModel

from nuclia import REGIONAL
from nuclia.exceptions import NuaAPIException
from nuclia_models.predict.generative_responses import (
    GenerativeChunk,
    GenerativeFullResponse,
    JSONGenerativeResponse,
    TextGenerativeResponse,
    CitationsGenerativeResponse,
    MetaGenerativeResponse,
    StatusGenerativeResponse,
)
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
    QueryInfo,
    RephraseModel,
    RestrictedIDString,
    Sentence,
    Source,
    StoredLearningConfiguration,
    SummarizedModel,
    SummarizeModel,
    SummarizeResource,
    Tokens,
)
from nuclia_models.predict.remi import RemiRequest, RemiResponse
import os
from tqdm import tqdm
import asyncio

MB = 1024 * 1024
CHUNK_SIZE = 10 * MB
SENTENCE_PREDICT = "/api/v1/predict/sentence"
CHAT_PREDICT = "/api/v1/predict/chat"
SUMMARIZE_PREDICT = "/api/v1/predict/summarize"
REPHRASE_PREDICT = "/api/v1/predict/rephrase"
TOKENS_PREDICT = "/api/v1/predict/tokens"
QUERY_PREDICT = "/api/v1/predict/query"
REMI_PREDICT = "/api/v1/predict/remi"
UPLOAD_PROCESS = "/api/v1/processing/upload"
STATUS_PROCESS = "/api/v2/processing/status"
PUSH_PROCESS = "/api/v2/processing/push"
SCHEMA = "/api/v1/learning/configuration/schema"
SCHEMA_KBID = "/api/v1/schema"
CONFIG = "/api/v1/config"

ConvertType = TypeVar("ConvertType", bound=BaseModel)


class Author(str, Enum):
    NUCLIA = "NUCLIA"
    USER = "USER"


class ContextItem(BaseModel):
    author: Author
    text: str


class NuaClient:
    def __init__(
        self,
        region: str,
        account: str,
        token: Optional[str] = None,
        headers: Optional[dict[str, str]] = None,
    ):
        self.region = region
        self.account = account
        self.token = token
        if "http" in region:
            self.url = region.strip("/")
        else:
            self.url = REGIONAL.format(region=region).strip("/")

        if token is None and headers is not None:
            self.headers = headers
        else:
            self.headers = {"X-STF-NUAKEY": f"Bearer {token}"}

        self.stream_headers = self.headers.copy()
        self.stream_headers["Accept"] = "application/x-ndjson"
        self.client = Client(headers=self.headers, base_url=self.url)
        self.stream_client = Client(headers=self.stream_headers, base_url=self.url)

    def _request(
        self,
        method: str,
        url: str,
        output: Type[ConvertType],
        payload: Optional[dict[Any, Any]] = None,
        timeout: int = 60,
    ) -> ConvertType:
        resp = self.client.request(method, url, json=payload, timeout=timeout)
        if resp.status_code != 200:
            raise NuaAPIException(code=resp.status_code, detail=resp.content.decode())
        try:
            data = output.model_validate(resp.json())
        except Exception:
            data = output.model_validate(resp.content)
        return data

    def _stream(
        self,
        method: str,
        url: str,
        payload: Optional[dict[Any, Any]] = None,
        timeout: int = 60,
    ) -> Iterator[GenerativeChunk]:
        with self.stream_client.stream(
            method,
            url,
            json=payload,
            timeout=timeout,
        ) as response:
            for json_body in response.iter_lines():
                yield GenerativeChunk.model_validate_json(json_body)  # type: ignore

    def add_config_predict(self, kbid: str, config: LearningConfigurationCreation):
        endpoint = f"{self.url}{CONFIG}/{kbid}"
        self._request(
            "POST", endpoint, payload=config.dict(exclude_none=True), output=Empty
        )

    def del_config_predict(self, kbid: str):
        endpoint = f"{self.url}{CONFIG}/{kbid}"
        self._request("DELETE", endpoint, output=Empty)

    def update_config_predict(self, kbid: str, config: LearningConfigurationUpdate):
        endpoint = f"{self.url}{CONFIG}/{kbid}"
        self._request(
            "POST", endpoint, payload=config.dict(exclude_none=True), output=Empty
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

    def query_predict(
        self,
        text: str,
        semantic_model: Optional[str] = None,
        token_model: Optional[str] = None,
        generative_model: Optional[str] = None,
    ) -> QueryInfo:
        endpoint = f"{self.url}{QUERY_PREDICT}?text={text}"
        if semantic_model:
            endpoint += f"&semantic_model={semantic_model}"
        if token_model:
            endpoint += f"&token_model={token_model}"
        if generative_model:
            endpoint += f"&generative_model={generative_model}"
        return self._request("GET", endpoint, output=QueryInfo)

    def generate(
        self, body: ChatModel, model: Optional[str] = None, timeout: int = 300
    ) -> GenerativeFullResponse:
        endpoint = f"{self.url}{CHAT_PREDICT}"
        if model:
            endpoint += f"?model={model}"

        result = GenerativeFullResponse(answer="")
        for chunk in self._stream(
            "POST",
            endpoint,
            payload=body.model_dump(),
            timeout=timeout,
        ):
            if isinstance(chunk.chunk, TextGenerativeResponse):
                result.answer += chunk.chunk.text
            elif isinstance(chunk.chunk, JSONGenerativeResponse):
                result.object = chunk.chunk.object
            elif isinstance(chunk.chunk, MetaGenerativeResponse):
                result.input_tokens = chunk.chunk.input_tokens
                result.output_tokens = chunk.chunk.output_tokens
                result.input_nuclia_tokens = chunk.chunk.input_nuclia_tokens
                result.output_nuclia_tokens = chunk.chunk.output_nuclia_tokens
                result.timings = chunk.chunk.timings
            elif isinstance(chunk.chunk, CitationsGenerativeResponse):
                result.citations = chunk.chunk.citations
            elif isinstance(chunk.chunk, StatusGenerativeResponse):
                result.code = chunk.chunk.code
        return result

    def generate_stream(
        self, body: ChatModel, model: Optional[str] = None, timeout: int = 300
    ) -> Iterator[GenerativeChunk]:
        endpoint = f"{self.url}{CHAT_PREDICT}"
        if model:
            endpoint += f"?model={model}"

        for gr in self._stream(
            "POST",
            endpoint,
            payload=body.model_dump(),
            timeout=timeout,
        ):
            yield gr

    def summarize(
        self, documents: dict[str, str], model: Optional[str] = None, timeout: int = 300
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
            "POST",
            endpoint,
            payload=body.model_dump(),
            output=SummarizedModel,
            timeout=timeout,
        )

    def rephrase(
        self,
        question: str,
        user_context: Optional[list[str]] = None,
        context: Optional[list[Union[dict, ContextItem]]] = None,
        model: Optional[str] = None,
        prompt: Optional[str] = None,
    ) -> RephraseModel:
        endpoint = f"{self.url}{REPHRASE_PREDICT}"
        if model:
            endpoint += f"?model={model}"

        body: dict[str, Any] = {
            "question": question,
            "user_context": user_context,
            "user_id": "USER",
        }
        if prompt:
            body["prompt"] = prompt
        if context:
            body["context"] = [
                c.model_dump(mode="json") if isinstance(c, BaseModel) else c
                for c in context
            ]
        return self._request(
            "POST",
            endpoint,
            payload=body,
            output=RephraseModel,
        )

    def remi(
        self,
        request: RemiRequest,
    ) -> RemiResponse:
        endpoint = f"{self.url}{REMI_PREDICT}"
        return self._request(
            "POST",
            endpoint,
            payload=request.model_dump(),
            output=RemiResponse,
        )

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
            "POST",
            process_endpoint,
            payload=payload.model_dump(),
            output=PushResponseV2,
        )

    def process_link(
        self,
        url: str,
        kbid: Optional[str] = None,
        headers: dict[str, str] = {},
        cookies: dict[str, str] = {},
        localstorage: dict[str, str] = {},
    ) -> PushResponseV2:
        payload = PushPayload(
            uuid=None, source=Source.HTTP, kbid=RestrictedIDString(kbid)
        )

        payload.linkfield["link"] = LinkUpload(
            link=url, headers=headers, cookies=cookies, localstorage=localstorage
        )
        process_endpoint = f"{self.url}{PUSH_PROCESS}"
        return self._request(
            "POST",
            process_endpoint,
            payload=payload.model_dump(),
            output=PushResponseV2,
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
    def __init__(
        self,
        region: str,
        account: str,
        token: Optional[str] = None,
        headers: Optional[dict[str, str]] = None,
    ):
        self.region = region
        self.account = account
        self.token = token
        if "http" in region:
            self.url = region.strip("/")
        else:
            self.url = REGIONAL.format(region=region).strip("/")
        if token is None and headers is not None:
            self.headers = headers
        else:
            self.headers = {"X-STF-NUAKEY": f"Bearer {token}"}

        self.stream_headers = self.headers.copy()
        self.stream_headers["Accept"] = "application/x-ndjson"

        self.client = AsyncClient(headers=self.headers, base_url=self.url)
        self.stream_client = AsyncClient(headers=self.stream_headers, base_url=self.url)

    async def _request(
        self,
        method: str,
        url: str,
        output: Type[ConvertType],
        payload: Optional[dict[Any, Any]] = None,
        timeout: int = 60,
    ) -> ConvertType:
        resp = await self.client.request(method, url, json=payload, timeout=timeout)
        if resp.status_code != 200:
            raise NuaAPIException(code=resp.status_code, detail=resp.content.decode())
        try:
            data = output.model_validate(resp.json())
        except Exception:
            data = output.model_validate(resp.content)
        return data

    async def _stream(
        self,
        method: str,
        url: str,
        payload: Optional[dict[Any, Any]] = None,
        timeout: int = 60,
    ) -> AsyncIterator[GenerativeChunk]:
        async with self.stream_client.stream(
            method,
            url,
            json=payload,
            timeout=timeout,
        ) as response:
            async for json_body in response.aiter_lines():
                yield GenerativeChunk.model_validate_json(json_body)  # type: ignore

    async def add_config_predict(
        self, kbid: str, config: LearningConfigurationCreation
    ):
        endpoint = f"{self.url}{CONFIG}/{kbid}"
        await self._request(
            "POST", endpoint, payload=config.dict(exclude_none=True), output=Empty
        )

    async def del_config_predict(self, kbid: str):
        endpoint = f"{self.url}{CONFIG}/{kbid}"
        await self._request("DELETE", endpoint, output=Empty)

    async def update_config_predict(
        self, kbid: str, config: LearningConfigurationUpdate
    ):
        endpoint = f"{self.url}{CONFIG}/{kbid}"
        await self._request(
            "POST", endpoint, payload=config.dict(exclude_none=True), output=Empty
        )

    async def schema_predict(self, kbid: Optional[str] = None) -> ConfigSchema:
        endpoint = f"{self.url}{SCHEMA}"
        if kbid is not None:
            endpoint = f"{self.url}{SCHEMA_KBID}/{kbid}"
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

    async def query_predict(
        self,
        text: str,
        semantic_model: Optional[str] = None,
        token_model: Optional[str] = None,
        generative_model: Optional[str] = None,
    ) -> QueryInfo:
        endpoint = f"{self.url}{QUERY_PREDICT}?text={text}"
        if semantic_model:
            endpoint += f"&semantic_model={semantic_model}"
        if token_model:
            endpoint += f"&token_model={token_model}"
        if generative_model:
            endpoint += f"&generative_model={generative_model}"
        return await self._request("GET", endpoint, output=QueryInfo)

    @deprecated(version="2.1.0", reason="You should use generate function")
    async def generate_predict(
        self, body: ChatModel, model: Optional[str] = None, timeout: int = 300
    ) -> ChatResponse:
        endpoint = f"{self.url}{CHAT_PREDICT}"
        if model:
            endpoint += f"?model={model}"

        return await self._request(
            "POST",
            endpoint,
            payload=body.model_dump(),
            output=ChatResponse,
            timeout=timeout,
        )

    async def generate(
        self, body: ChatModel, model: Optional[str] = None, timeout: int = 300
    ) -> GenerativeFullResponse:
        endpoint = f"{self.url}{CHAT_PREDICT}"
        if model:
            endpoint += f"?model={model}"
        result = GenerativeFullResponse(answer="")

        async for chunk in self._stream(
            "POST",
            endpoint,
            payload=body.model_dump(),
            timeout=timeout,
        ):
            if isinstance(chunk.chunk, TextGenerativeResponse):
                result.answer += chunk.chunk.text
            elif isinstance(chunk.chunk, JSONGenerativeResponse):
                result.object = chunk.chunk.object
            elif isinstance(chunk.chunk, MetaGenerativeResponse):
                result.input_tokens = chunk.chunk.input_tokens
                result.output_tokens = chunk.chunk.output_tokens
                result.input_nuclia_tokens = chunk.chunk.input_nuclia_tokens
                result.output_nuclia_tokens = chunk.chunk.output_nuclia_tokens
                result.timings = chunk.chunk.timings
            elif isinstance(chunk.chunk, CitationsGenerativeResponse):
                result.citations = chunk.chunk.citations
            elif isinstance(chunk.chunk, StatusGenerativeResponse):
                result.code = chunk.chunk.code
        return result

    async def generate_stream(
        self, body: ChatModel, model: Optional[str] = None, timeout: int = 300
    ) -> AsyncIterator[GenerativeChunk]:
        endpoint = f"{self.url}{CHAT_PREDICT}"
        if model:
            endpoint += f"?model={model}"

        async for gr in self._stream(
            "POST",
            endpoint,
            payload=body.model_dump(),
            timeout=timeout,
        ):
            yield gr

    async def summarize(
        self, documents: dict[str, str], model: Optional[str] = None, timeout: int = 300
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
            "POST",
            endpoint,
            payload=body.model_dump(),
            output=SummarizedModel,
            timeout=timeout,
        )

    async def rephrase(
        self,
        question: str,
        user_context: Optional[list[str]] = None,
        context: Optional[list[Union[dict, ContextItem]]] = None,
        model: Optional[str] = None,
        prompt: Optional[str] = None,
    ) -> RephraseModel:
        endpoint = f"{self.url}{REPHRASE_PREDICT}"
        if model:
            endpoint += f"?model={model}"

        body: dict[str, Any] = {
            "question": question,
            "user_context": user_context,
            "user_id": "USER",
        }
        if prompt:
            body["prompt"] = prompt
        if context:
            body["context"] = [
                c.model_dump(mode="json") if isinstance(c, BaseModel) else c
                for c in context
            ]
        return await self._request(
            "POST",
            endpoint,
            payload=body,
            output=RephraseModel,
        )

    async def remi(self, request: RemiRequest) -> RemiResponse:
        endpoint = f"{self.url}{REMI_PREDICT}"
        return await self._request(
            "POST",
            endpoint,
            payload=request.model_dump(),
            output=RemiResponse,
        )

    async def generate_retrieval(
        self,
        question: str,
        context: list[str],
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
            "POST", endpoint, payload=body.model_dump(), output=ChatResponse
        )

    async def process_link(
        self,
        url: str,
        kbid: Optional[str] = None,
        headers: dict[str, str] = {},
        cookies: dict[str, str] = {},
        localstorage: dict[str, str] = {},
    ) -> PushResponseV2:
        payload = PushPayload(
            uuid=None, source=Source.HTTP, kbid=RestrictedIDString(kbid)
        )

        payload.linkfield["link"] = LinkUpload(
            link=url, headers=headers, cookies=cookies, localstorage=localstorage
        )
        process_endpoint = f"{self.url}{PUSH_PROCESS}"
        return await self._request(
            "POST",
            process_endpoint,
            payload=payload.model_dump(),
            output=PushResponseV2,
        )

    async def process_file(
        self, path: str, kbid: Optional[str] = None
    ) -> PushResponseV2:
        filename = path.split("/")[-1]
        upload_endpoint = f"{self.url}{UPLOAD_PROCESS}"

        headers = self.headers.copy()
        headers["X-FILENAME"] = base64.b64encode(filename.encode()).decode()

        async def iterator(path: str):
            total_size = os.path.getsize(path)
            with tqdm(
                desc="Uploading data",
                total=total_size,
                unit="iB",
                unit_scale=True,
            ) as pbar:
                async with aiofiles.open(path, "rb") as f:
                    while True:
                        chunk = await f.read(CHUNK_SIZE)
                        if not chunk:
                            break
                        pbar.update(len(chunk))
                        yield chunk

        resp = await self.client.post(
            upload_endpoint, content=iterator(path), headers=headers
        )

        payload = PushPayload(
            uuid=None, source=Source.HTTP, kbid=RestrictedIDString(kbid)
        )

        payload.filefield[filename] = resp.content.decode()
        process_endpoint = f"{self.url}{PUSH_PROCESS}"
        return await self._request(
            "POST",
            process_endpoint,
            payload=payload.model_dump(),
            output=PushResponseV2,
        )

    async def wait_for_processing(
        self, response: PushResponseV2, timeout: int = 30
    ) -> Optional[BrokerMessage]:
        status = await self.processing_id_status(response.processing_id)
        count = timeout
        while status.completed is False and status.failed is False and count > 0:
            status = await self.processing_id_status(response.processing_id)
            await asyncio.sleep(1)
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
