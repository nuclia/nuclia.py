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
    Iterator,
    Optional,
    Type,
    TypeVar,
    Union,
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
from nucliadb_models.internal.predict import (
    QueryInfo as PredictQueryInfo,
)
from nucliadb_models.internal.predict import (
    RerankModel,
    RerankResponse,
)
from nucliadb_models.search import Image as PredictImage
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


class Author(str, Enum):
    NUCLIA = "NUCLIA"
    USER = "USER"


class ContextItem(BaseModel):
    author: Author
    text: str


class AsyncNuaEndpoint(str, Enum):
    """Endpoint profile used by :class:`AsyncNuaClient`."""

    PUBLIC = "public"
    INTERNAL = "internal"
    ONPREM = "onprem"


@dataclass
class PredictRephraseResponse:
    """Result of a KB-aware Predict rephrase request."""

    rephrased_query: str
    use_chat_history: bool | None = None
    learning_id: str | None = None
    model: str | None = None


class PredictQueryRequest(BaseModel):
    """Request payload for the current KB-aware Predict query endpoint."""

    text: str | None = None
    query_image: PredictImage | None = None
    rephrase: bool = False
    rephrase_prompt: str | None = None
    generative_model: str | None = None
    semantic_models: list[str] | None = None
    agentic_entities: bool = False
    graph_nodes: list[str] | None = None
    semantic_graph_node_models: list[str] | None = None
    graph_edges: list[str] | None = None
    semantic_graph_edge_models: list[str] | None = None


class PredictRephraseRequest(BaseModel):
    """Request payload for the KB-aware Predict rephrase endpoint."""

    question: str
    user_id: str
    chat_history: list[ContextItem] = Field(default_factory=list)
    user_context: list[str] = Field(default_factory=list)
    generative_model: str | None = None
    chat_history_relevance_threshold: float | None = None


class PredictRephraseError(Exception):
    """Predict could not rephrase the supplied query."""


class PredictRephraseMissingContextError(PredictRephraseError):
    """Predict could not rephrase because the supplied context was insufficient."""


class NuaKeyMissingError(Exception):
    """An on-prem Predict request requires a service account or local Predict."""


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
        self.client = build_httpx_client(headers=self.headers, base_url=self.url)
        self.stream_client = build_httpx_client(
            headers=self.stream_headers, base_url=self.url
        )

    def _request(
        self,
        method: str,
        url: str,
        output: Optional[Type[ConvertType]] = None,
        payload: Optional[dict[Any, Any]] = None,
        extra_headers: Optional[dict[str, str]] = None,
        timeout: int = 60,
    ) -> ConvertType:
        resp = self.client.request(
            method, url, json=payload, timeout=timeout, headers=extra_headers
        )
        if resp.status_code in (429, 512):
            raise RetriableRequestException(
                code=resp.status_code, detail=resp.content.decode()
            )
        elif resp.status_code > 299:
            raise NuaAPIException(code=resp.status_code, detail=resp.content.decode())
        if output is None:
            return None  # type: ignore
        try:
            data = output.model_validate(resp.json())
        except Exception:
            data = output.model_validate(resp.content)
        return data

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
            if response.headers.get("transfer-encoding") == "chunked":
                for json_body in response.iter_lines():
                    try:
                        chunk = GenerativeChunk.model_validate_json(json_body)  # type: ignore
                        if chunk.chunk.type == "meta":
                            chunk.chunk.learning_id = response.headers.get(
                                "nuclia-learning-id", chunk.chunk.learning_id
                            )
                            chunk.chunk.model_name = response.headers.get(
                                "nuclia-learning-model", chunk.chunk.model_name
                            )
                            chunk.chunk.trace_id = response.headers.get(
                                "nuclia-learning-trace-id", chunk.chunk.trace_id
                            )
                        yield chunk
                    except ValidationError as e:
                        raise RuntimeError(f"Invalid stream chunk: {json_body}") from e

            else:
                # Read the full error body and raise an appropriate exception
                response.read()
                error_content = response.content
                raise RuntimeError(
                    f"Stream request failed with status {response.status_code}: {error_content.decode('utf-8')}"
                )

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

    def config_predict(self, kbid: str) -> StoredLearningConfiguration:
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
        endpoint = f"{self.url}{SENTENCE_PREDICT}?text={text}"
        if model:
            endpoint += f"&model={model}"
        return self._request(
            "GET", endpoint, output=Sentence, extra_headers=extra_headers
        )

    def tokens_predict(
        self,
        text: str,
        model: Optional[str] = None,
        extra_headers: Optional[dict[str, str]] = None,
    ) -> Tokens:
        endpoint = f"{self.url}{TOKENS_PREDICT}?text={text}"
        if model:
            endpoint += f"&model={model}"
        return self._request(
            "GET", endpoint, output=Tokens, extra_headers=extra_headers
        )

    def query_predict(
        self,
        text: str,
        semantic_model: Optional[str] = None,
        token_model: Optional[str] = None,
        generative_model: Optional[str] = None,
        extra_headers: Optional[dict[str, str]] = None,
    ) -> QueryInfo:
        endpoint = f"{self.url}{QUERY_PREDICT}?text={text}"
        if semantic_model:
            endpoint += f"&semantic_model={semantic_model}"
        if token_model:
            endpoint += f"&token_model={token_model}"
        if generative_model:
            endpoint += f"&generative_model={generative_model}"
        return self._request(
            "GET", endpoint, output=QueryInfo, extra_headers=extra_headers
        )

    def generate(
        self,
        body: ChatModel,
        model: Optional[str] = None,
        extra_headers: Optional[dict[str, str]] = None,
        timeout: int = 300,
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

    def generate_stream(
        self,
        body: ChatModel,
        model: Optional[str] = None,
        extra_headers: Optional[dict[str, str]] = None,
        timeout: int = 300,
    ) -> Iterator[GenerativeChunk]:
        endpoint = f"{self.url}{CHAT_PREDICT}"
        if model:
            endpoint += f"?model={model}"

        for gr in self._stream(
            "POST",
            endpoint,
            payload=body.model_dump(),
            timeout=timeout,
            extra_headers=extra_headers,
        ):
            yield gr

    def summarize(
        self,
        documents: dict[str, str],
        model: Optional[str] = None,
        extra_headers: Optional[dict[str, str]] = None,
        timeout: int = 300,
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
            extra_headers=extra_headers,
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
        extra_headers: Optional[dict[str, str]] = None,
        timeout: int = 120,
    ) -> RemiResponse:
        endpoint = f"{self.url}{REMI_PREDICT}"
        return self._request(
            "POST",
            endpoint,
            extra_headers=extra_headers,
            payload=request.model_dump(),
            output=RemiResponse,
            timeout=timeout,
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
    ) -> RerankResponse:
        endpoint = f"{self.url}{RERANK}"
        return self._request(
            "POST",
            endpoint,
            payload=model.model_dump(),
            output=RerankResponse,
            extra_headers=extra_headers,
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
        if "http" in region:
            self.url = region.strip("/")
        else:
            self.url = REGIONAL.format(region=region).strip("/")

        if endpoint is AsyncNuaEndpoint.INTERNAL:
            self.headers = {"X-STF-KBID": kbid} if kbid else {}
            if account:
                self.headers["X-STF-ACCOUNT"] = account
            if headers:
                self.headers.update(headers)
        elif endpoint is AsyncNuaEndpoint.ONPREM:
            self.headers = (
                {"X-STF-NUAKEY": f"Bearer {service_account}"}
                if service_account is not None
                else {}
            )
            if local_predict_headers is not None:
                self.headers.update(local_predict_headers)
        elif token is None and headers is not None:
            self.headers = headers.copy()
        else:
            self.headers = {"X-STF-NUAKEY": f"Bearer {token}"}

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
        if self.endpoint is not AsyncNuaEndpoint.ONPREM:
            return
        if not self.local_predict and "X-STF-NUAKEY" not in self.headers:
            raise NuaKeyMissingError(
                "An on-prem Predict request requires a Nuclia service account "
                "unless local Predict is enabled."
            )
        if kbid or self.kbid:
            return
        raise ValueError("An on-prem Predict request requires a knowledge box ID.")

    def _predict_endpoint(self, operation: str, kbid: str | None = None) -> str:
        if self.endpoint is AsyncNuaEndpoint.INTERNAL:
            path = f"{INTERNAL_PREDICT}/{operation}"
        else:
            path = f"{PUBLIC_PREDICT}/{operation}"

        if self.endpoint is AsyncNuaEndpoint.ONPREM:
            resolved_kbid = kbid or self.kbid
            if resolved_kbid:
                path = f"{path}/{resolved_kbid}"
        return f"{self.url}{path}"

    def _headers_for(
        self,
        kbid: str | None = None,
        extra_headers: dict[str, str] | None = None,
    ) -> dict[str, str] | None:
        headers = self.headers.copy()
        if self.endpoint is AsyncNuaEndpoint.INTERNAL and kbid is not None:
            headers["X-STF-KBID"] = kbid
        if extra_headers:
            headers.update(extra_headers)
        return headers or None

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
        self._raise_for_response(resp, error_type)
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
        self._raise_for_response(response, error_type)
        return response

    def _response_detail(self, response: Response) -> str:
        try:
            data = response.json()
        except ValueError:
            return response.text
        if isinstance(data, dict) and "detail" in data:
            return str(data["detail"])
        return str(data)

    def _raise_for_response(
        self, response: Response, error_type: type[NuaAPIException]
    ) -> None:
        if response.status_code < 300:
            return
        detail = self._response_detail(response)
        if response.status_code in (429, 512):
            if error_type is PredictAPIException:
                raise RetriablePredictAPIException(
                    code=response.status_code, detail=detail
                )
            raise RetriableRequestException(code=response.status_code, detail=detail)
        if error_type is PredictAPIException and response.status_code == 402:
            raise PredictLimitsExceededError(code=response.status_code, detail=detail)
        raise error_type(code=response.status_code, detail=detail)

    async def _check_stream_response(
        self,
        response: Response,
        error_type: type[NuaAPIException] = NuaAPIException,
    ) -> None:
        if response.status_code > 299:
            await response.aread()
        self._raise_for_response(response, error_type)

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

    async def tokens_predict(
        self,
        text: str,
        model: Optional[str] = None,
        extra_headers: Optional[dict[str, str]] = None,
    ) -> Tokens:
        endpoint = f"{self._predict_endpoint('tokens')}?text={text}"
        if model:
            endpoint += f"&model={model}"
        return await self._request(
            "GET", endpoint, output=Tokens, extra_headers=extra_headers
        )

    async def query_predict(
        self,
        text: str,
        semantic_model: Optional[str] = None,
        token_model: Optional[str] = None,
        generative_model: Optional[str] = None,
        extra_headers: Optional[dict[str, str]] = None,
    ) -> QueryInfo:
        endpoint = f"{self._predict_endpoint('query')}?text={text}"
        if semantic_model:
            endpoint += f"&semantic_model={semantic_model}"
        if token_model:
            endpoint += f"&token_model={token_model}"
        if generative_model:
            endpoint += f"&generative_model={generative_model}"
        return await self._request(
            "GET", endpoint, output=QueryInfo, extra_headers=extra_headers
        )

    async def predict_query(
        self,
        request: PredictQueryRequest,
        kbid: str | None = None,
        extra_headers: Optional[dict[str, str]] = None,
        timeout: int = 60,
    ) -> PredictQueryInfo:
        """Call the current KB-aware Predict query endpoint."""

        self._validate_predict_request(kbid)
        return await self._request(
            "POST",
            self._predict_endpoint("query", kbid),
            payload=request.model_dump(mode="json", exclude_none=True),
            output=PredictQueryInfo,
            extra_headers=self._headers_for(kbid, extra_headers),
            timeout=timeout,
            error_type=PredictAPIException,
        )

    async def predict_tokens(
        self,
        text: str,
        kbid: str | None = None,
        model: Optional[str] = None,
        extra_headers: Optional[dict[str, str]] = None,
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

    async def generate_stream(
        self,
        body: ChatModel,
        model: Optional[str] = None,
        extra_headers: Optional[dict[str, str]] = None,
        timeout: int = 300,
    ) -> AsyncIterator[GenerativeChunk]:
        endpoint = self._predict_endpoint("chat")
        if model:
            endpoint += f"?model={model}"

        async for gr in self._stream(
            "POST",
            endpoint,
            payload=body.model_dump(),
            timeout=timeout,
            extra_headers=extra_headers,
        ):
            yield gr

    async def predict_chat_stream(
        self,
        body: ChatModel,
        kbid: str | None = None,
        extra_headers: Optional[dict[str, str]] = None,
        timeout: Timeout | float | None = Timeout(30.0, read=None),
    ) -> tuple[str, str, AsyncIterator[GenerativeChunk]]:
        """Open a KB-aware Predict chat stream."""

        self._validate_predict_request(kbid)
        headers = self._headers_for(kbid, extra_headers) or {}
        headers.setdefault("Accept", "application/x-ndjson")
        request = self.stream_client.build_request(
            "POST",
            self._predict_endpoint("chat", kbid),
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

        return learning_id, model, stream()

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

    async def rephrase(
        self,
        question: str,
        user_context: Optional[list[str]] = None,
        context: Optional[list[Union[dict, ContextItem]]] = None,
        model: Optional[str] = None,
        prompt: Optional[str] = None,
    ) -> RephraseModel:
        endpoint = self._predict_endpoint("rephrase")
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
            "POST", endpoint, payload=body, output=RephraseModel, timeout=120
        )

    async def predict_rephrase(
        self,
        body: PredictRephraseRequest,
        kbid: str | None = None,
        extra_headers: Optional[dict[str, str]] = None,
        timeout: int = 120,
    ) -> PredictRephraseResponse:
        """Call Predict's KB-aware rephrase endpoint."""

        self._validate_predict_request(kbid)
        response = await self._request_raw(
            "POST",
            self._predict_endpoint("rephrase", kbid),
            payload=body.model_dump(mode="json"),
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
        if content.endswith("-1"):
            raise PredictRephraseError(content[:-2])
        if content.endswith("-2"):
            raise PredictRephraseMissingContextError(content[:-2])
        if content.endswith("0"):
            content = content[:-1]

        return PredictRephraseResponse(
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
        self, model: RerankModel, extra_headers: Optional[dict[str, str]] = None
    ) -> RerankResponse:
        return await self.predict_rerank(model, extra_headers=extra_headers)

    async def predict_rerank(
        self,
        model: RerankModel,
        kbid: str | None = None,
        extra_headers: Optional[dict[str, str]] = None,
        timeout: int = 60,
    ) -> RerankResponse:
        """Call the KB-aware Predict rerank endpoint."""

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
