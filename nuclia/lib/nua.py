import asyncio
import base64
import os
from dataclasses import dataclass
from enum import Enum
from time import sleep
from typing import (
    TYPE_CHECKING,
    Any,
    AsyncIterator,
    Awaitable,
    Callable,
    Coroutine,
    Generic,
    Iterator,
    Literal,
    Optional,
    Type,
    TypeAlias,
    TypeVar,
    overload,
)
from urllib.parse import urlencode

import aiofiles
import backoff
from deprecated import deprecated
from httpx import ConnectError, ConnectTimeout, Response, Timeout
from nuclia_models.common.consumption import Consumption, ConsumptionGenerative
from nuclia_models.predict.generative_responses import (
    CitationsGenerativeResponse,
    FootnoteCitationsGenerativeResponse,
    GenerativeChunk,
    GenerativeFullResponse,
    JSONGenerativeResponse,
    MetaGenerativeResponse,
    ReasoningGenerativeResponse,
    StatusGenerativeResponse,
    TextGenerativeResponse,
    ToolsGenerativeResponse,
)
from nuclia_models.predict.remi import RemiRequest, RemiResponse
from nucliadb_models.search import Image
from pydantic import BaseModel, Field, ValidationError
from tqdm import tqdm

from nuclia import REGIONAL
from nuclia.exceptions import (
    NuaAPIException,
    PredictAPIException,
    PredictLimitsExceededError,
    RetriablePredictAPIException,
)
from nuclia.lib.nua_responses import (
    ChatModel,
    ChatResponse,
    ConfigSchema,
    Empty,
    LearningConfigurationCreation,
    LearningConfigurationUpdate,
    LinkUpload,
    Message,
    ProcessRequestStatus,
    ProcessRequestStatusResults,
    PushPayload,
    PushResponseV2,
    QueryInfo,
    RephraseModel,
    RerankModel,
    RerankResponse,
    RestrictedIDString,
    Sentence,
    Source,
    StoredLearningConfiguration,
    SummarizedModel,
    SummarizeModel,
    SummarizeResource,
    Tokens,
)
from nuclia.lib.utils import build_httpx_async_client, build_httpx_client

if TYPE_CHECKING:
    from nucliadb_protos.writer_pb2 import (
        BrokerMessage,  # type: ignore[import-not-found]
    )

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
RERANK = "/api/v1/predict/rerank"
INTERNAL_PREDICT = "/api/internal/predict"
PUBLIC_PREDICT = "/api/v1/predict"
LEARNING_ID_HEADER = "nuclia-learning-id"
LEARNING_MODEL_HEADER = "nuclia-learning-model"
LEARNING_TRACE_HEADER = "nuclia-learning-trace-id"
LEARNING_CHAT_HISTORY_HEADER = "nuclia-learning-chat-history"

ConvertType = TypeVar("ConvertType", bound=BaseModel)
StreamType = TypeVar("StreamType")


# Backward-compatible name for the shared chat-history message model.
ContextItem: TypeAlias = Message


class AsyncNuaEndpoint(str, Enum):
    """Endpoint profile used by :class:`AsyncNuaClient`."""

    PUBLIC = "public"
    INTERNAL = "internal"
    ONPREM = "onprem"


class QueryRequest(BaseModel):
    """Request payload for the Predict query endpoint."""

    text: str | None = None
    query_image: Image | None = None
    rephrase: bool = False
    rephrase_prompt: str | None = None
    generative_model: str | None = None
    semantic_models: list[str] | None = None
    semantic_model: str | None = None
    token_model: str | None = None
    agentic_entities: bool = False
    graph_nodes: list[str] | None = None
    semantic_graph_node_models: list[str] | None = None
    graph_edges: list[str] | None = None
    semantic_graph_edge_models: list[str] | None = None


class RephraseRequest(BaseModel):
    """Request payload for the Predict rephrase endpoint."""

    question: str
    user_id: str = "system"
    chat_history: list[ContextItem] = Field(default_factory=list)
    context: list[ContextItem | dict[str, Any]] = Field(default_factory=list)
    user_context: list[str] = Field(default_factory=list)
    generative_model: str | None = None
    prompt: str | None = None
    chat_history_relevance_threshold: float | None = None


@dataclass
class GenerateStreamResponse(Generic[StreamType]):
    """Metadata and chunks returned by a Predict chat stream."""

    learning_id: str
    model: str
    stream: StreamType


class AsyncGenerateStream(
    AsyncIterator[GenerativeChunk],
    Awaitable[GenerateStreamResponse[AsyncIterator[GenerativeChunk]]],
):
    """A chat stream that supports both legacy iteration and metadata access."""

    def __init__(
        self,
        open_stream: Callable[
            [],
            Coroutine[
                None, None, GenerateStreamResponse[AsyncIterator[GenerativeChunk]]
            ],
        ],
    ):
        self._open_stream = open_stream
        self._response: (
            Awaitable[GenerateStreamResponse[AsyncIterator[GenerativeChunk]]] | None
        ) = None
        self._iterator: AsyncIterator[GenerativeChunk] | None = None

    async def _get_response(
        self,
    ) -> GenerateStreamResponse[AsyncIterator[GenerativeChunk]]:
        if self._response is None:
            self._response = asyncio.create_task(self._open_stream())
        return await self._response

    def __await__(self):
        return self._get_response().__await__()

    def __aiter__(self) -> "AsyncGenerateStream":
        return self

    async def __anext__(self) -> GenerativeChunk:
        if self._iterator is None:
            self._iterator = (await self).stream
        return await self._iterator.__anext__()


class PredictRephraseError(Exception):
    """Predict could not rephrase the supplied query."""


class PredictRephraseMissingContextError(PredictRephraseError):
    """Predict could not rephrase because the supplied context was insufficient."""


class NuaKeyMissingError(Exception):
    """An on-prem Predict request requires a service account or local Predict."""


def _resolve_url(region: str) -> str:
    return (
        region.strip("/")
        if "http" in region
        else REGIONAL.format(region=region).strip("/")
    )


def _build_headers(
    *,
    endpoint: AsyncNuaEndpoint,
    account: str,
    token: str | None,
    headers: dict[str, str] | None,
    kbid: str | None,
    service_account: str | None,
    local_predict_headers: dict[str, str] | None,
) -> dict[str, str]:
    if endpoint is AsyncNuaEndpoint.INTERNAL:
        result = {"X-STF-KBID": kbid} if kbid else {}
        if account:
            result["X-STF-ACCOUNT"] = account
        if headers:
            result.update(headers)
        return result
    if endpoint is AsyncNuaEndpoint.ONPREM:
        result = (
            {"X-STF-NUAKEY": f"Bearer {service_account}"}
            if service_account is not None
            else {}
        )
        if local_predict_headers:
            result.update(local_predict_headers)
        return result
    if token is None and headers is not None:
        return headers.copy()
    return {"X-STF-NUAKEY": f"Bearer {token}"}


def _validate_predict_request(
    *,
    endpoint: AsyncNuaEndpoint,
    headers: dict[str, str],
    local_predict: bool,
    configured_kbid: str | None,
    kbid: str | None,
) -> None:
    if endpoint is not AsyncNuaEndpoint.ONPREM:
        return
    if not local_predict and "X-STF-NUAKEY" not in headers:
        raise NuaKeyMissingError(
            "An on-prem Predict request requires a Nuclia service account "
            "unless local Predict is enabled."
        )


def _predict_endpoint(
    *,
    url: str,
    endpoint: AsyncNuaEndpoint,
    configured_kbid: str | None,
    operation: str,
    kbid: str | None,
) -> str:
    path = (
        f"{INTERNAL_PREDICT}/{operation}"
        if endpoint is AsyncNuaEndpoint.INTERNAL
        else f"{PUBLIC_PREDICT}/{operation}"
    )
    if endpoint is AsyncNuaEndpoint.ONPREM:
        resolved_kbid = kbid or configured_kbid
        if resolved_kbid:
            path = f"{path}/{resolved_kbid}"
    return f"{url}{path}"


def _headers_for(
    *,
    headers: dict[str, str],
    endpoint: AsyncNuaEndpoint,
    kbid: str | None,
    extra_headers: dict[str, str] | None,
) -> dict[str, str] | None:
    result = headers.copy()
    if endpoint is AsyncNuaEndpoint.INTERNAL and kbid is not None:
        result["X-STF-KBID"] = kbid
    if extra_headers:
        result.update(extra_headers)
    return result or None


def _response_detail(response: Response) -> str:
    try:
        data = response.json()
    except ValueError:
        return response.text
    if isinstance(data, dict) and "detail" in data:
        return str(data["detail"])
    return str(data)


def _raise_for_response(response: Response, error_type: type[NuaAPIException]) -> None:
    if response.status_code < 300:
        return
    detail = _response_detail(response)
    if response.status_code in (429, 512):
        if error_type is PredictAPIException:
            raise RetriablePredictAPIException(code=response.status_code, detail=detail)
        raise RetriableRequestException(code=response.status_code, detail=detail)
    if error_type is PredictAPIException and response.status_code == 402:
        raise PredictLimitsExceededError(code=response.status_code, detail=detail)
    raise error_type(code=response.status_code, detail=detail)


class NuaClient:
    def __init__(
        self,
        region: str,
        account: str,
        token: Optional[str] = None,
        headers: Optional[dict[str, str]] = None,
        *,
        endpoint: AsyncNuaEndpoint = AsyncNuaEndpoint.PUBLIC,
        kbid: str | None = None,
        service_account: str | None = None,
        local_predict: bool = False,
        local_predict_headers: dict[str, str] | None = None,
    ):
        self.region = region
        self.account = account
        self.token = token
        self.endpoint = endpoint
        self.kbid = kbid
        self.local_predict = local_predict
        self.url = _resolve_url(region)
        self.headers = _build_headers(
            endpoint=endpoint,
            account=account,
            token=token,
            headers=headers,
            kbid=kbid,
            service_account=service_account,
            local_predict_headers=local_predict_headers,
        )

        self.stream_headers = self.headers.copy()
        self.stream_headers["Accept"] = "application/x-ndjson"
        self.client = build_httpx_client(headers=self.headers, base_url=self.url)
        self.stream_client = build_httpx_client(
            headers=self.stream_headers, base_url=self.url
        )

    @classmethod
    def internal(
        cls,
        url: str,
        kbid: str | None = None,
        account: str | None = None,
        headers: dict[str, str] | None = None,
    ) -> "NuaClient":
        """Create a client for the hosted internal Predict API."""

        return cls(
            region=url,
            account=account or "",
            headers=headers,
            endpoint=AsyncNuaEndpoint.INTERNAL,
            kbid=kbid,
        )

    @classmethod
    def onprem(
        cls,
        public_url: str,
        service_account: str | None = None,
        zone: str | None = None,
        kbid: str | None = None,
        local_predict: bool = False,
        local_predict_headers: dict[str, str] | None = None,
    ) -> "NuaClient":
        """Create a client for the public, KB-scoped on-prem Predict API."""

        url = public_url.format(zone=zone) if zone is not None else public_url
        return cls(
            region=url,
            account="",
            endpoint=AsyncNuaEndpoint.ONPREM,
            kbid=kbid,
            service_account=None if local_predict else service_account,
            local_predict=local_predict,
            local_predict_headers=local_predict_headers,
        )

    def _validate_predict_request(self, kbid: str | None = None) -> None:
        _validate_predict_request(
            endpoint=self.endpoint,
            headers=self.headers,
            local_predict=self.local_predict,
            configured_kbid=self.kbid,
            kbid=kbid,
        )

    def _predict_endpoint(self, operation: str, kbid: str | None = None) -> str:
        return _predict_endpoint(
            url=self.url,
            endpoint=self.endpoint,
            configured_kbid=self.kbid,
            operation=operation,
            kbid=kbid,
        )

    def _headers_for(
        self,
        kbid: str | None = None,
        extra_headers: dict[str, str] | None = None,
    ) -> dict[str, str] | None:
        return _headers_for(
            headers=self.headers,
            endpoint=self.endpoint,
            kbid=kbid,
            extra_headers=extra_headers,
        )

    def _raise_for_response(
        self, response: Response, error_type: type[NuaAPIException]
    ) -> None:
        _raise_for_response(response, error_type)

    def close(self) -> None:
        """Close the underlying HTTP clients."""

        self.client.close()
        self.stream_client.close()

    def __enter__(self) -> "NuaClient":
        return self

    def __exit__(self, exc_type, exc_value, traceback) -> None:
        self.close()

    def _request(
        self,
        method: str,
        url: str,
        output: Optional[Type[ConvertType]] = None,
        payload: Optional[dict[Any, Any]] = None,
        extra_headers: Optional[dict[str, str]] = None,
        timeout: int = 60,
        error_type: type[NuaAPIException] = NuaAPIException,
    ) -> ConvertType:
        resp = self.client.request(
            method, url, json=payload, timeout=timeout, headers=extra_headers
        )
        _raise_for_response(resp, error_type)
        if output is None:
            return None  # type: ignore
        try:
            data = output.model_validate(resp.json())
        except Exception:
            data = output.model_validate(resp.content)
        return data

    def _request_raw(
        self,
        method: str,
        url: str,
        payload: Optional[dict[Any, Any]] = None,
        extra_headers: Optional[dict[str, str]] = None,
        timeout: int = 60,
        error_type: type[NuaAPIException] = NuaAPIException,
    ) -> Response:
        response = self.client.request(
            method,
            url,
            json=payload,
            timeout=timeout,
            headers=extra_headers,
        )
        _raise_for_response(response, error_type)
        return response

    def _stream(
        self,
        method: str,
        url: str,
        extra_headers: Optional[dict[str, str]] = None,
        payload: Optional[dict[Any, Any]] = None,
        timeout: int = 60,
    ) -> Iterator[GenerativeChunk]:
        with self.stream_client.stream(
            method,
            url,
            json=payload,
            timeout=timeout,
            headers=extra_headers,
        ) as response:
            _raise_for_response(response, PredictAPIException)
            for json_body in response.iter_lines():
                if not json_body.strip():
                    continue
                try:
                    chunk = GenerativeChunk.model_validate_json(json_body)
                    if chunk.chunk.type == "meta":
                        chunk.chunk.learning_id = response.headers.get(
                            LEARNING_ID_HEADER, chunk.chunk.learning_id
                        )
                        chunk.chunk.model_name = response.headers.get(
                            LEARNING_MODEL_HEADER, chunk.chunk.model_name
                        )
                        chunk.chunk.trace_id = response.headers.get(
                            LEARNING_TRACE_HEADER, chunk.chunk.trace_id
                        )
                    yield chunk
                except ValidationError as e:
                    raise RuntimeError(f"Invalid stream chunk: {json_body}") from e

    def add_config_predict(self, kbid: str, config: LearningConfigurationCreation):
        endpoint = f"{self.url}{CONFIG}/{kbid}"
        self._request(
            "POST", endpoint, payload=config.dict(exclude_none=True), output=Empty
        )

    def del_config_predict(self, kbid: str):
        endpoint = f"{self.url}{CONFIG}/{kbid}"
        self._request("DELETE", endpoint, output=None)

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

    def config_predict(self, kbid: Optional[str] = None) -> StoredLearningConfiguration:
        endpoint = f"{self.url}{CONFIG}"
        if kbid is not None:
            endpoint = f"{self.url}{CONFIG}/{kbid}"
        return self._request("GET", endpoint, output=StoredLearningConfiguration)

    def sentence_predict(
        self,
        text: str,
        model: Optional[str] = None,
        extra_headers: Optional[dict[str, str]] = None,
    ) -> Sentence:
        endpoint = f"{self._predict_endpoint('sentence')}?text={text}"
        if model:
            endpoint += f"&model={model}"
        return self._request(
            "GET", endpoint, output=Sentence, extra_headers=extra_headers
        )

    @overload
    def query_predict(
        self,
        request: str,
        semantic_model: str | None = None,
        token_model: str | None = None,
        generative_model: str | None = None,
        extra_headers: dict[str, str] | None = None,
    ) -> QueryInfo: ...

    @overload
    def query_predict(
        self,
        request: QueryRequest,
        semantic_model: None = None,
        token_model: None = None,
        generative_model: None = None,
        extra_headers: dict[str, str] | None = None,
        *,
        kbid: str | None = None,
        timeout: int = 60,
    ) -> QueryInfo: ...

    def query_predict(
        self,
        request: str | QueryRequest,
        semantic_model: str | None = None,
        token_model: str | None = None,
        generative_model: str | None = None,
        extra_headers: Optional[dict[str, str]] = None,
        *,
        kbid: str | None = None,
        timeout: int = 60,
    ) -> QueryInfo:
        """Call the Predict query endpoint."""

        if isinstance(request, str):
            endpoint = f"{self._predict_endpoint('query')}?text={request}"
            if semantic_model:
                endpoint += f"&semantic_model={semantic_model}"
            if token_model:
                endpoint += f"&token_model={token_model}"
            if generative_model:
                endpoint += f"&generative_model={generative_model}"
            return self._request(
                "GET", endpoint, output=QueryInfo, extra_headers=extra_headers
            )

        self._validate_predict_request(kbid)
        return self._request(
            "POST",
            self._predict_endpoint("query", kbid),
            payload=request.model_dump(mode="json", exclude_none=True),
            output=QueryInfo,
            extra_headers=self._headers_for(kbid, extra_headers),
            timeout=timeout,
            error_type=PredictAPIException,
        )

    def tokens_predict(
        self,
        text: str,
        model: Optional[str] = None,
        extra_headers: Optional[dict[str, str]] = None,
        *,
        kbid: str | None = None,
        timeout: int = 60,
    ) -> Tokens:
        """Call Predict's token endpoint."""

        self._validate_predict_request(kbid)
        params = {"text": text}
        if model is not None:
            params["model"] = model
        endpoint = f"{self._predict_endpoint('tokens', kbid)}?{urlencode(params)}"
        return self._request(
            "GET",
            endpoint,
            output=Tokens,
            extra_headers=self._headers_for(kbid, extra_headers),
            timeout=timeout,
            error_type=PredictAPIException,
        )

    def generate(
        self,
        body: ChatModel,
        model: Optional[str] = None,
        extra_headers: Optional[dict[str, str]] = None,
        timeout: int = 300,
    ) -> GenerativeFullResponse:
        endpoint = self._predict_endpoint("chat")
        if model:
            endpoint += f"?model={model}"

        result = GenerativeFullResponse(answer="")
        for chunk in self._stream(
            "POST",
            endpoint,
            payload=body.model_dump(),
            timeout=timeout,
            extra_headers=extra_headers,
        ):
            if isinstance(chunk.chunk, TextGenerativeResponse):
                result.answer += chunk.chunk.text
            elif isinstance(chunk.chunk, ReasoningGenerativeResponse):
                result.reasoning = (result.reasoning or "") + chunk.chunk.text
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
            elif isinstance(chunk.chunk, FootnoteCitationsGenerativeResponse):
                result.citation_footnote_to_context = chunk.chunk.footnote_to_context
            elif isinstance(chunk.chunk, StatusGenerativeResponse):
                result.code = chunk.chunk.code
            elif isinstance(chunk.chunk, ToolsGenerativeResponse):
                result.tools = chunk.chunk.tools
            elif isinstance(chunk.chunk, ConsumptionGenerative):
                result.consumption = Consumption(
                    normalized_tokens=chunk.chunk.normalized_tokens,
                    customer_key_tokens=chunk.chunk.customer_key_tokens,
                )
        return result

    @deprecated(version="2.1.0", reason="You should use generate function")
    def generate_predict(
        self, body: ChatModel, model: Optional[str] = None, timeout: int = 300
    ) -> ChatResponse:
        endpoint = self._predict_endpoint("chat")
        if model:
            endpoint += f"?model={model}"
        return self._request(
            "POST",
            endpoint,
            payload=body.model_dump(),
            output=ChatResponse,
            timeout=timeout,
        )

    @overload
    def generate_stream(
        self,
        body: ChatModel,
        model: str | None = None,
        extra_headers: dict[str, str] | None = None,
        timeout: int = 300,
        *,
        kbid: str | None = None,
        return_metadata: Literal[False] = False,
    ) -> Iterator[GenerativeChunk]: ...

    @overload
    def generate_stream(
        self,
        body: ChatModel,
        model: str | None = None,
        extra_headers: dict[str, str] | None = None,
        timeout: Timeout | float | None = Timeout(30.0, read=None),
        *,
        kbid: str | None = None,
        return_metadata: Literal[True],
    ) -> GenerateStreamResponse[Iterator[GenerativeChunk]]: ...

    def generate_stream(
        self,
        body: ChatModel,
        model: str | None = None,
        extra_headers: Optional[dict[str, str]] = None,
        timeout: Timeout | float | None = 300,
        *,
        kbid: str | None = None,
        return_metadata: bool = False,
    ) -> Iterator[GenerativeChunk] | GenerateStreamResponse[Iterator[GenerativeChunk]]:
        """Open a Predict chat stream."""

        if return_metadata and timeout == 300:
            timeout = Timeout(30.0, read=None)
        self._validate_predict_request(kbid)
        headers = self._headers_for(kbid, extra_headers) or {}
        headers.setdefault("Accept", "application/x-ndjson")
        endpoint = self._predict_endpoint("chat", kbid)
        if model is not None and not (kbid or self.kbid):
            endpoint = f"{endpoint}?model={model}"
        request = self.stream_client.build_request(
            "POST",
            endpoint,
            json=body.model_dump(mode="json"),
            headers=headers,
            timeout=timeout,
        )
        response = self.stream_client.send(request, stream=True)
        try:
            _raise_for_response(response, PredictAPIException)
        except Exception:
            response.close()
            raise
        learning_id = response.headers.get(LEARNING_ID_HEADER, "unknown")
        model = response.headers.get(LEARNING_MODEL_HEADER, "unknown")

        def stream() -> Iterator[GenerativeChunk]:
            try:
                for json_body in response.iter_lines():
                    if not json_body.strip():
                        continue
                    yield GenerativeChunk.model_validate_json(json_body)
            finally:
                response.close()

        result = GenerateStreamResponse(learning_id, model, stream())
        return result if return_metadata else result.stream

    def summarize(
        self,
        documents: dict[str, str],
        model: Optional[str] = None,
        extra_headers: Optional[dict[str, str]] = None,
        timeout: int = 300,
    ) -> SummarizedModel:
        endpoint = self._predict_endpoint("summarize")
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
            extra_headers=extra_headers,
        )

    @overload
    def rephrase(
        self,
        question: str,
        user_context: list[str] | None = None,
        context: list[dict[Any, Any] | ContextItem] | None = None,
        model: str | None = None,
        prompt: str | None = None,
    ) -> RephraseModel: ...

    @overload
    def rephrase(
        self,
        question: RephraseRequest,
        user_context: None = None,
        context: None = None,
        model: None = None,
        prompt: None = None,
        *,
        kbid: str | None = None,
        extra_headers: dict[str, str] | None = None,
        timeout: int = 120,
    ) -> RephraseModel: ...

    def rephrase(
        self,
        question: str | RephraseRequest,
        user_context: list[str] | None = None,
        context: list[dict[Any, Any] | ContextItem] | None = None,
        model: str | None = None,
        prompt: str | None = None,
        *,
        kbid: str | None = None,
        extra_headers: Optional[dict[str, str]] = None,
        timeout: int = 120,
    ) -> RephraseModel:
        """Call Predict's rephrase endpoint."""

        if isinstance(question, str):
            endpoint = self._predict_endpoint("rephrase")
            if model:
                endpoint += f"?model={model}"
            payload: dict[str, Any] = {
                "question": question,
                "user_context": user_context,
                "user_id": "USER",
            }
            if prompt:
                payload["prompt"] = prompt
            if context:
                payload["context"] = [
                    item.model_dump(mode="json")
                    if isinstance(item, BaseModel)
                    else item
                    for item in context
                ]
            return self._request(
                "POST", endpoint, payload=payload, output=RephraseModel, timeout=120
            )

        self._validate_predict_request(kbid)
        response = self._request_raw(
            "POST",
            self._predict_endpoint("rephrase", kbid),
            payload=question.model_dump(mode="json"),
            extra_headers=self._headers_for(kbid, extra_headers),
            timeout=timeout,
            error_type=PredictAPIException,
        )
        try:
            content = response.json()
            headers = response.headers
        finally:
            response.close()
        if not isinstance(content, str):
            raise PredictRephraseError("Predict returned an invalid rephrase response")
        return RephraseModel(
            rephrased_query=content,
            use_chat_history=(
                headers[LEARNING_CHAT_HISTORY_HEADER].lower() == "true"
                if LEARNING_CHAT_HISTORY_HEADER in headers
                else None
            ),
            learning_id=headers.get(LEARNING_ID_HEADER),
            model=headers.get(LEARNING_MODEL_HEADER),
        )

    def remi(
        self,
        request: RemiRequest,
        extra_headers: Optional[dict[str, str]] = None,
        timeout: int = 120,
    ) -> RemiResponse:
        endpoint = self._predict_endpoint("remi")
        return self._request(
            "POST",
            endpoint,
            extra_headers=extra_headers,
            payload=request.model_dump(),
            output=RemiResponse,
            timeout=timeout,
        )

    def generate_retrieval(
        self,
        question: str,
        context: list[str],
        model: Optional[str] = None,
    ) -> ChatResponse:
        endpoint = self._predict_endpoint("chat")
        if model:
            endpoint += f"?model={model}"
        body = ChatModel(
            question=question,
            retrieval=True,
            user_id="Nuclia PY CLI",
            query_context=context,
        )
        return self._request(
            "POST",
            endpoint,
            payload=body.model_dump(),
            output=ChatResponse,
            timeout=300,
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
    ) -> Optional["BrokerMessage"]:
        try:
            from nucliadb_protos.writer_pb2 import BrokerMessage
        except ImportError:
            raise ImportError(
                "The 'nucliadb_protos' library is required to use this functionality. "
                "Install it with: pip install nuclia[protos]"
            )

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

    def rerank(
        self,
        model: RerankModel,
        extra_headers: Optional[dict[str, str]] = None,
        *,
        kbid: str | None = None,
        timeout: int = 60,
    ) -> RerankResponse:
        """Call Predict's rerank endpoint."""

        self._validate_predict_request(kbid)
        return self._request(
            "POST",
            self._predict_endpoint("rerank", kbid),
            payload=model.model_dump(mode="json"),
            output=RerankResponse,
            extra_headers=self._headers_for(kbid, extra_headers),
            timeout=timeout,
            error_type=PredictAPIException,
        )


class RetriableRequestException(NuaAPIException):
    pass


class AsyncNuaClient:
    def __init__(
        self,
        region: str,
        account: str,
        token: Optional[str] = None,
        headers: Optional[dict[str, str]] = None,
        *,
        endpoint: AsyncNuaEndpoint = AsyncNuaEndpoint.PUBLIC,
        kbid: str | None = None,
        service_account: str | None = None,
        local_predict: bool = False,
        local_predict_headers: dict[str, str] | None = None,
    ):
        self.region = region
        self.account = account
        self.token = token
        self.endpoint = endpoint
        self.kbid = kbid
        self.local_predict = local_predict
        self.url = _resolve_url(region)
        self.headers = _build_headers(
            endpoint=endpoint,
            account=account,
            token=token,
            headers=headers,
            kbid=kbid,
            service_account=service_account,
            local_predict_headers=local_predict_headers,
        )

        self.stream_headers = self.headers.copy()
        self.stream_headers["Accept"] = "application/x-ndjson"

        self.client = build_httpx_async_client(headers=self.headers, base_url=self.url)
        self.stream_client = build_httpx_async_client(
            headers=self.stream_headers, base_url=self.url
        )

    @classmethod
    def internal(
        cls,
        url: str,
        kbid: str | None = None,
        account: str | None = None,
        headers: dict[str, str] | None = None,
    ) -> "AsyncNuaClient":
        """Create a client for the hosted internal Predict API."""

        client = cls(
            region=url,
            account=account or "",
            headers=headers,
            endpoint=AsyncNuaEndpoint.INTERNAL,
            kbid=kbid,
        )
        return client

    @classmethod
    def onprem(
        cls,
        public_url: str,
        service_account: str | None = None,
        zone: str | None = None,
        kbid: str | None = None,
        local_predict: bool = False,
        local_predict_headers: dict[str, str] | None = None,
    ) -> "AsyncNuaClient":
        """Create a client for the public, KB-scoped on-prem Predict API."""

        url = public_url.format(zone=zone) if zone is not None else public_url
        return cls(
            region=url,
            account="",
            endpoint=AsyncNuaEndpoint.ONPREM,
            kbid=kbid,
            service_account=None if local_predict else service_account,
            local_predict=local_predict,
            local_predict_headers=local_predict_headers,
        )

    def _validate_predict_request(self, kbid: str | None = None) -> None:
        _validate_predict_request(
            endpoint=self.endpoint,
            headers=self.headers,
            local_predict=self.local_predict,
            configured_kbid=self.kbid,
            kbid=kbid,
        )

    def _predict_endpoint(self, operation: str, kbid: str | None = None) -> str:
        return _predict_endpoint(
            url=self.url,
            endpoint=self.endpoint,
            configured_kbid=self.kbid,
            operation=operation,
            kbid=kbid,
        )

    def _headers_for(
        self,
        kbid: str | None = None,
        extra_headers: dict[str, str] | None = None,
    ) -> dict[str, str] | None:
        return _headers_for(
            headers=self.headers,
            endpoint=self.endpoint,
            kbid=kbid,
            extra_headers=extra_headers,
        )

    def _raise_for_response(
        self, response: Response, error_type: type[NuaAPIException]
    ) -> None:
        _raise_for_response(response, error_type)

    async def aclose(self) -> None:
        """Close the underlying HTTP clients."""

        await self.client.aclose()
        await self.stream_client.aclose()

    async def __aenter__(self) -> "AsyncNuaClient":
        return self

    async def __aexit__(self, exc_type, exc_value, traceback) -> None:
        await self.aclose()

    @backoff.on_exception(
        backoff.expo,
        (
            ConnectError,
            ConnectTimeout,
            RetriableRequestException,
            RetriablePredictAPIException,
        ),
        max_time=60,
        jitter=backoff.full_jitter,
    )
    async def _request(
        self,
        method: str,
        url: str,
        output: Optional[Type[ConvertType]] = None,
        payload: Optional[dict[Any, Any]] = None,
        extra_headers: Optional[dict[str, str]] = None,
        timeout: int = 60,
        error_type: type[NuaAPIException] = NuaAPIException,
    ) -> ConvertType:
        resp = await self.client.request(
            method, url, json=payload, timeout=timeout, headers=extra_headers
        )
        _raise_for_response(resp, error_type)
        if output is None:
            return None  # type: ignore
        try:
            data = output.model_validate(resp.json())
        except Exception:
            data = output.model_validate(resp.content)
        return data

    @backoff.on_exception(
        backoff.expo,
        (
            ConnectError,
            ConnectTimeout,
            RetriableRequestException,
            RetriablePredictAPIException,
        ),
        max_time=60,
        jitter=backoff.full_jitter,
    )
    async def _request_raw(
        self,
        method: str,
        url: str,
        payload: Optional[dict[Any, Any]] = None,
        extra_headers: Optional[dict[str, str]] = None,
        timeout: int = 60,
        error_type: type[NuaAPIException] = NuaAPIException,
    ) -> Response:
        response = await self.client.request(
            method,
            url,
            json=payload,
            timeout=timeout,
            headers=extra_headers,
        )
        _raise_for_response(response, error_type)
        return response

    async def _check_stream_response(
        self,
        response: Response,
        error_type: type[NuaAPIException] = NuaAPIException,
    ) -> None:
        if response.status_code > 299:
            await response.aread()
        _raise_for_response(response, error_type)

    async def _parse_stream(self, response: Response) -> AsyncIterator[GenerativeChunk]:
        async for json_body in response.aiter_lines():
            if not json_body.strip():
                continue
            try:
                chunk = GenerativeChunk.model_validate_json(json_body)
                if chunk.chunk.type == "meta":
                    chunk.chunk.learning_id = response.headers.get(
                        LEARNING_ID_HEADER, chunk.chunk.learning_id
                    )
                    chunk.chunk.model_name = response.headers.get(
                        LEARNING_MODEL_HEADER, chunk.chunk.model_name
                    )
                    chunk.chunk.trace_id = response.headers.get(
                        LEARNING_TRACE_HEADER, chunk.chunk.trace_id
                    )
                yield chunk
            except ValidationError as e:
                raise RuntimeError(f"Invalid stream chunk: {json_body}") from e

    @backoff.on_exception(
        backoff.expo,
        (
            ConnectError,
            ConnectTimeout,
            RetriableRequestException,
            RetriablePredictAPIException,
        ),
        max_time=60,
        jitter=backoff.full_jitter,
    )
    async def _stream(
        self,
        method: str,
        url: str,
        extra_headers: Optional[dict[str, str]] = None,
        payload: Optional[dict[Any, Any]] = None,
        timeout: int = 60,
    ) -> AsyncIterator[GenerativeChunk]:
        async with self.stream_client.stream(
            method,
            url,
            json=payload,
            timeout=timeout,
            headers=extra_headers,
        ) as response:
            await self._check_stream_response(response)
            async for chunk in self._parse_stream(response):
                yield chunk

    async def add_config_predict(
        self, kbid: str, config: LearningConfigurationCreation
    ):
        endpoint = f"{self.url}{CONFIG}/{kbid}"
        await self._request(
            "POST", endpoint, payload=config.dict(exclude_none=True), output=Empty
        )

    async def del_config_predict(self, kbid: str):
        endpoint = f"{self.url}{CONFIG}/{kbid}"
        await self._request("DELETE", endpoint, output=None)

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
        self,
        text: str,
        model: Optional[str] = None,
        extra_headers: Optional[dict[str, str]] = None,
    ) -> Sentence:
        endpoint = f"{self._predict_endpoint('sentence')}?text={text}"
        if model:
            endpoint += f"&model={model}"
        return await self._request(
            "GET", endpoint, output=Sentence, extra_headers=extra_headers
        )

    @overload
    async def query_predict(
        self,
        request: str,
        semantic_model: str | None = None,
        token_model: str | None = None,
        generative_model: str | None = None,
        extra_headers: dict[str, str] | None = None,
    ) -> QueryInfo: ...

    @overload
    async def query_predict(
        self,
        request: QueryRequest,
        semantic_model: None = None,
        token_model: None = None,
        generative_model: None = None,
        extra_headers: dict[str, str] | None = None,
        *,
        kbid: str | None = None,
        timeout: int = 60,
    ) -> QueryInfo: ...

    async def query_predict(
        self,
        request: str | QueryRequest,
        semantic_model: str | None = None,
        token_model: str | None = None,
        generative_model: str | None = None,
        extra_headers: Optional[dict[str, str]] = None,
        *,
        kbid: str | None = None,
        timeout: int = 60,
    ) -> QueryInfo:
        """Call the Predict query endpoint."""

        if isinstance(request, str):
            endpoint = f"{self._predict_endpoint('query')}?text={request}"
            if semantic_model:
                endpoint += f"&semantic_model={semantic_model}"
            if token_model:
                endpoint += f"&token_model={token_model}"
            if generative_model:
                endpoint += f"&generative_model={generative_model}"
            return await self._request(
                "GET", endpoint, output=QueryInfo, extra_headers=extra_headers
            )

        self._validate_predict_request(kbid)
        return await self._request(
            "POST",
            self._predict_endpoint("query", kbid),
            payload=request.model_dump(mode="json", exclude_none=True),
            output=QueryInfo,
            extra_headers=self._headers_for(kbid, extra_headers),
            timeout=timeout,
            error_type=PredictAPIException,
        )

    async def tokens_predict(
        self,
        text: str,
        model: Optional[str] = None,
        extra_headers: Optional[dict[str, str]] = None,
        *,
        kbid: str | None = None,
        timeout: int = 60,
    ) -> Tokens:
        """Call Predict's token endpoint for a hosted or on-prem KB."""

        self._validate_predict_request(kbid)
        params = {"text": text}
        if model is not None:
            params["model"] = model
        endpoint = f"{self._predict_endpoint('tokens', kbid)}?{urlencode(params)}"
        return await self._request(
            "GET",
            endpoint,
            output=Tokens,
            extra_headers=self._headers_for(kbid, extra_headers),
            timeout=timeout,
            error_type=PredictAPIException,
        )

    @deprecated(version="2.1.0", reason="You should use generate function")
    async def generate_predict(
        self, body: ChatModel, model: Optional[str] = None, timeout: int = 300
    ) -> ChatResponse:
        endpoint = self._predict_endpoint("chat")
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
        self,
        body: ChatModel,
        model: Optional[str] = None,
        extra_headers: Optional[dict[str, str]] = None,
        timeout: int = 300,
    ) -> GenerativeFullResponse:
        endpoint = self._predict_endpoint("chat")
        if model:
            endpoint += f"?model={model}"
        result = GenerativeFullResponse(answer="")

        async for chunk in self._stream(
            "POST",
            endpoint,
            payload=body.model_dump(),
            timeout=timeout,
            extra_headers=extra_headers,
        ):
            if isinstance(chunk.chunk, TextGenerativeResponse):
                result.answer += chunk.chunk.text
            elif isinstance(chunk.chunk, ReasoningGenerativeResponse):
                result.reasoning = (result.reasoning or "") + chunk.chunk.text
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
            elif isinstance(chunk.chunk, FootnoteCitationsGenerativeResponse):
                result.citation_footnote_to_context = chunk.chunk.footnote_to_context
            elif isinstance(chunk.chunk, StatusGenerativeResponse):
                result.code = chunk.chunk.code
            elif isinstance(chunk.chunk, ToolsGenerativeResponse):
                result.tools = chunk.chunk.tools
            elif isinstance(chunk.chunk, ConsumptionGenerative):
                result.consumption = Consumption(
                    normalized_tokens=chunk.chunk.normalized_tokens,
                    customer_key_tokens=chunk.chunk.customer_key_tokens,
                )

        return result

    @overload
    def generate_stream(
        self,
        body: ChatModel,
        model: str | None = None,
        extra_headers: dict[str, str] | None = None,
        timeout: int = 300,
        *,
        kbid: str | None = None,
        return_metadata: Literal[False] = False,
    ) -> AsyncIterator[GenerativeChunk]: ...

    @overload
    def generate_stream(
        self,
        body: ChatModel,
        model: str | None = None,
        extra_headers: dict[str, str] | None = None,
        timeout: Timeout | float | None = Timeout(30.0, read=None),
        *,
        kbid: str | None = None,
        return_metadata: Literal[True],
    ) -> Awaitable[GenerateStreamResponse[AsyncIterator[GenerativeChunk]]]: ...

    def generate_stream(
        self,
        body: ChatModel,
        model: str | None = None,
        extra_headers: Optional[dict[str, str]] = None,
        timeout: Timeout | float | None = 300,
        *,
        kbid: str | None = None,
        return_metadata: bool = False,
    ) -> AsyncGenerateStream:
        if return_metadata and timeout == 300:
            timeout = Timeout(30.0, read=None)
        return AsyncGenerateStream(
            lambda: self._open_generate_stream(
                body, model, extra_headers, timeout, kbid
            )
        )

    async def _open_generate_stream(
        self,
        body: ChatModel,
        model: str | None,
        extra_headers: dict[str, str] | None,
        timeout: Timeout | float | None,
        kbid: str | None,
    ) -> GenerateStreamResponse[AsyncIterator[GenerativeChunk]]:
        """Open a Predict chat stream."""

        self._validate_predict_request(kbid)
        headers = self._headers_for(kbid, extra_headers) or {}
        headers.setdefault("Accept", "application/x-ndjson")
        endpoint = self._predict_endpoint("chat", kbid)
        if model is not None and not (kbid or self.kbid):
            endpoint = f"{endpoint}?model={model}"
        request = self.stream_client.build_request(
            "POST",
            endpoint,
            json=body.model_dump(mode="json"),
            headers=headers,
            timeout=timeout,
        )
        response = await self.stream_client.send(request, stream=True)
        try:
            await self._check_stream_response(response, PredictAPIException)
        except Exception:
            await response.aclose()
            raise
        learning_id = response.headers.get(LEARNING_ID_HEADER, "unknown")
        model = response.headers.get(LEARNING_MODEL_HEADER, "unknown")

        async def stream() -> AsyncIterator[GenerativeChunk]:
            try:
                async for chunk in self._parse_stream(response):
                    yield chunk
            finally:
                await response.aclose()

        return GenerateStreamResponse(learning_id, model, stream())

    async def summarize(
        self,
        documents: dict[str, str],
        model: Optional[str] = None,
        extra_headers: Optional[dict[str, str]] = None,
        timeout: int = 300,
    ) -> SummarizedModel:
        endpoint = self._predict_endpoint("summarize")
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
            extra_headers=extra_headers,
        )

    @overload
    async def rephrase(
        self,
        question: str,
        user_context: list[str] | None = None,
        context: list[dict[Any, Any] | ContextItem] | None = None,
        model: str | None = None,
        prompt: str | None = None,
    ) -> RephraseModel: ...

    @overload
    async def rephrase(
        self,
        question: RephraseRequest,
        user_context: None = None,
        context: None = None,
        model: None = None,
        prompt: None = None,
        *,
        kbid: str | None = None,
        extra_headers: dict[str, str] | None = None,
        timeout: int = 120,
    ) -> RephraseModel: ...

    async def rephrase(
        self,
        question: str | RephraseRequest,
        user_context: list[str] | None = None,
        context: list[dict[Any, Any] | ContextItem] | None = None,
        model: str | None = None,
        prompt: str | None = None,
        *,
        kbid: str | None = None,
        extra_headers: Optional[dict[str, str]] = None,
        timeout: int = 120,
    ) -> RephraseModel:
        """Call Predict's rephrase endpoint."""

        if isinstance(question, str):
            endpoint = self._predict_endpoint("rephrase")
            if model:
                endpoint += f"?model={model}"
            payload: dict[str, Any] = {
                "question": question,
                "user_context": user_context,
                "user_id": "USER",
            }
            if prompt:
                payload["prompt"] = prompt
            if context:
                payload["context"] = [
                    item.model_dump(mode="json")
                    if isinstance(item, BaseModel)
                    else item
                    for item in context
                ]
            return await self._request(
                "POST", endpoint, payload=payload, output=RephraseModel, timeout=120
            )

        self._validate_predict_request(kbid)
        response = await self._request_raw(
            "POST",
            self._predict_endpoint("rephrase", kbid),
            payload=question.model_dump(mode="json"),
            extra_headers=self._headers_for(kbid, extra_headers),
            timeout=timeout,
            error_type=PredictAPIException,
        )
        try:
            content = response.json()
            headers = response.headers
        finally:
            await response.aclose()
        if not isinstance(content, str):
            raise PredictRephraseError("Predict returned an invalid rephrase response")
        return RephraseModel(
            rephrased_query=content,
            use_chat_history=(
                headers[LEARNING_CHAT_HISTORY_HEADER].lower() == "true"
                if LEARNING_CHAT_HISTORY_HEADER in headers
                else None
            ),
            learning_id=headers.get(LEARNING_ID_HEADER),
            model=headers.get(LEARNING_MODEL_HEADER),
        )

    async def remi(
        self,
        request: RemiRequest,
        extra_headers: Optional[dict[str, str]] = None,
        timeout: int = 120,
    ) -> RemiResponse:
        endpoint = self._predict_endpoint("remi")
        return await self._request(
            "POST",
            endpoint,
            payload=request.model_dump(),
            output=RemiResponse,
            extra_headers=extra_headers,
            timeout=timeout,
        )

    async def generate_retrieval(
        self,
        question: str,
        context: list[str],
        model: Optional[str] = None,
    ) -> ChatResponse:
        endpoint = self._predict_endpoint("chat")
        if model:
            endpoint += f"?model={model}"
        body = ChatModel(
            question=question,
            retrieval=True,
            user_id="Nuclia PY CLI",
            query_context=context,
        )
        return await self._request(
            "POST",
            endpoint,
            payload=body.model_dump(),
            output=ChatResponse,
            timeout=300,
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
    ) -> Optional["BrokerMessage"]:
        try:
            from nucliadb_protos.writer_pb2 import BrokerMessage
        except ImportError:
            raise ImportError(
                "The 'nucliadb_protos' library is required to use this functionality. "
                "Install it with: pip install nuclia[protos]"
            )

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

    async def rerank(
        self,
        model: RerankModel,
        extra_headers: Optional[dict[str, str]] = None,
        *,
        kbid: str | None = None,
        timeout: int = 60,
    ) -> RerankResponse:
        """Call Predict's rerank endpoint."""

        self._validate_predict_request(kbid)
        return await self._request(
            "POST",
            self._predict_endpoint("rerank", kbid),
            payload=model.model_dump(mode="json"),
            output=RerankResponse,
            extra_headers=self._headers_for(kbid, extra_headers),
            timeout=timeout,
            error_type=PredictAPIException,
        )
