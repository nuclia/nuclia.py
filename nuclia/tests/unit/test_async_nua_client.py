import json

import httpx
import pytest
from nuclia_models.predict.generative_responses import TextGenerativeResponse

from nuclia.exceptions import (
    PredictAPIException,
    PredictLimitsExceededError,
    RetriablePredictAPIException,
)
from nuclia.lib.nua import (
    AsyncNuaClient,
    NuaKeyMissingError,
    QueryRequest,
    RephraseRequest,
)
from nuclia.lib.nua_responses import ChatModel, QueryInfo, RephraseModel, RerankModel


def chunk(chunk_type: str, **data) -> str:
    return json.dumps({"chunk": {"type": chunk_type, **data}}) + "\n"


@pytest.mark.asyncio
async def test_internal_query_predict_uses_kbid_headers():
    requests = []

    async def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(
            200,
            json={
                "language": "en",
                "stop_words": [],
                "semantic_thresholds": {"model": 0.5},
                "visual_llm": False,
                "max_context": 1000,
                "entities": None,
                "sentence": None,
                "query": "hello",
                "rephrased_query": None,
            },
        )

    client = AsyncNuaClient.internal("http://predict", kbid="kb-1", account="account-1")
    client.client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    try:
        result = await client.query_predict(QueryRequest(text="hello"))
    finally:
        await client.aclose()

    assert result.query == "hello"
    assert requests[0].url == "http://predict/api/internal/predict/query"
    assert requests[0].headers["x-stf-kbid"] == "kb-1"
    assert requests[0].headers["x-stf-account"] == "account-1"
    assert requests[0].method == "POST"


@pytest.mark.asyncio
async def test_legacy_query_predict_uses_get_response_model():
    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.url == "http://predict/api/v1/predict/query?text=hello"
        return httpx.Response(
            200,
            json={
                "language": "en",
                "stop_words": [],
                "semantic_threshold": 0.5,
                "visual_llm": False,
                "max_context": 1000,
                "entities": None,
                "sentence": None,
            },
        )

    client = AsyncNuaClient("http://predict", account="")
    client.client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    try:
        result = await client.query_predict("hello")
    finally:
        await client.aclose()

    assert isinstance(result, QueryInfo)


@pytest.mark.asyncio
async def test_legacy_rephrase_uses_root_response_model():
    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.url == "http://predict/api/v1/predict/rephrase?model=model-1"
        return httpx.Response(200, json="new query")

    client = AsyncNuaClient("http://predict", account="")
    client.client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    try:
        result = await client.rephrase("old", model="model-1")
    finally:
        await client.aclose()

    assert isinstance(result, RephraseModel)
    assert result.rephrased_query == "new query"


@pytest.mark.asyncio
async def test_legacy_generate_stream_returns_async_iterator():
    client = AsyncNuaClient("http://predict", account="")
    client.stream_client = httpx.AsyncClient(
        transport=httpx.MockTransport(
            lambda _: httpx.Response(200, content=chunk("text", text="hello"))
        )
    )
    try:
        chunks = [
            chunk
            async for chunk in client.generate_stream(
                ChatModel(question="hello", user_id="user")
            )
        ]
    finally:
        await client.aclose()

    assert isinstance(chunks[0].chunk, TextGenerativeResponse)


@pytest.mark.asyncio
async def test_onprem_generate_stream_returns_headers_and_chunks():
    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.url == "http://predict/api/v1/predict/chat/kb-1"
        assert request.headers["x-stf-nuakey"] == "Bearer service-account"
        assert request.extensions["timeout"]["connect"] == 30.0
        assert request.extensions["timeout"]["read"] is None
        return httpx.Response(
            200,
            headers={
                "content-type": "application/x-ndjson",
                "nuclia-learning-id": "learning-1",
                "nuclia-learning-model": "model-1",
            },
            content=chunk("text", text="hello"),
        )

    client = AsyncNuaClient.onprem(
        "http://predict", service_account="service-account", kbid="kb-1"
    )
    client.stream_client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    try:
        response = await client.generate_stream(
            ChatModel(question="hello", user_id="user"), return_metadata=True
        )
        chunks = [item async for item in response.stream]
    finally:
        await client.aclose()

    assert response.learning_id == "learning-1"
    assert response.model == "model-1"
    assert isinstance(chunks[0].chunk, TextGenerativeResponse)
    assert chunks[0].chunk.text == "hello"


@pytest.mark.asyncio
async def test_onprem_rephrase_parses_headers():
    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.url == "http://predict/api/v1/predict/rephrase/kb-1"
        return httpx.Response(
            200,
            headers={
                "nuclia-learning-id": "learning-2",
                "nuclia-learning-model": "model-2",
                "nuclia-learning-chat-history": "false",
            },
            json="new query",
        )

    client = AsyncNuaClient.onprem(
        "http://predict", kbid="kb-1", service_account="service-account"
    )
    client.client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    try:
        result = await client.rephrase(RephraseRequest(question="old", user_id="user"))
    finally:
        await client.aclose()

    assert result.rephrased_query == "new query"
    assert result.use_chat_history is False
    assert result.learning_id == "learning-2"
    assert result.model == "model-2"


@pytest.mark.asyncio
async def test_onprem_rephrase_without_kbid_uses_base_endpoint():
    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.url == "http://predict/api/v1/predict/rephrase"
        return httpx.Response(200, json="new query")

    client = AsyncNuaClient.onprem("http://predict", service_account="service-account")
    client.client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    try:
        result = await client.rephrase(RephraseRequest(question="old"))
    finally:
        await client.aclose()

    assert result.rephrased_query == "new query"


@pytest.mark.asyncio
async def test_internal_rerank_uses_request_headers():
    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.url == "http://predict/api/internal/predict/rerank"
        assert request.headers["x-stf-kbid"] == "kb-1"
        return httpx.Response(200, json={"context_scores": {"1": 0.9}})

    client = AsyncNuaClient.internal("http://predict", kbid="kb-1")
    client.client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    try:
        result = await client.rerank(
            RerankModel(question="hello", user_id="user", context={"1": "text"})
        )
    finally:
        await client.aclose()

    assert result.context_scores == {"1": 0.9}


@pytest.mark.asyncio
async def test_onprem_rerank_without_kbid_uses_base_endpoint():
    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.url == "http://predict/api/v1/predict/rerank"
        return httpx.Response(200, json={"context_scores": {"1": 0.9}})

    client = AsyncNuaClient.onprem("http://predict", service_account="service-account")
    client.client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    try:
        result = await client.rerank(
            RerankModel(question="hello", user_id="user", context={"1": "text"})
        )
    finally:
        await client.aclose()

    assert result.context_scores == {"1": 0.9}


@pytest.mark.asyncio
async def test_tokens_predict_encodes_text_and_uses_kbid_override():
    async def handler(request: httpx.Request) -> httpx.Response:
        assert (
            request.url == "http://predict/api/internal/predict/tokens?text=hello+world"
        )
        assert request.headers["x-stf-kbid"] == "kb-2"
        return httpx.Response(200, json={"tokens": [], "time": 0})

    client = AsyncNuaClient.internal("http://predict", kbid="kb-1")
    client.client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    try:
        result = await client.tokens_predict("hello world", kbid="kb-2")
    finally:
        await client.aclose()

    assert result.tokens == []


@pytest.mark.asyncio
async def test_onprem_predict_requires_service_account():
    client = AsyncNuaClient.onprem("http://predict")
    try:
        with pytest.raises(NuaKeyMissingError):
            await client.tokens_predict("hello")
    finally:
        await client.aclose()

    requests = []

    async def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, json={"tokens": [], "time": 0})

    client = AsyncNuaClient.onprem("http://predict", service_account="service-account")
    client.client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    try:
        result = await client.tokens_predict("hello")
    finally:
        await client.aclose()

    assert result.tokens == []
    assert requests[0].url == "http://predict/api/v1/predict/tokens?text=hello"


@pytest.mark.asyncio
async def test_onprem_local_predict_allows_requests_without_service_account():
    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.url == "http://predict/api/v1/predict/tokens/kb-1?text=hello"
        return httpx.Response(200, json={"tokens": [], "time": 0})

    client = AsyncNuaClient.onprem("http://predict", kbid="kb-1", local_predict=True)
    client.client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    try:
        result = await client.tokens_predict("hello")
    finally:
        await client.aclose()

    assert result.tokens == []


@pytest.mark.asyncio
async def test_predict_limits_error_is_typed_and_includes_api_detail():
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(402, json={"detail": "monthly limit reached"})

    client = AsyncNuaClient.internal("http://predict", kbid="kb-1")
    client.client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    try:
        with pytest.raises(PredictLimitsExceededError) as error:
            await client.tokens_predict("hello")
    finally:
        await client.aclose()

    assert error.value.code == 402
    assert error.value.detail == "monthly limit reached"


@pytest.mark.asyncio
async def test_predict_errors_are_typed_and_include_plain_text_detail():
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(400, text="invalid query")

    client = AsyncNuaClient.internal("http://predict", kbid="kb-1")
    client.client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    try:
        with pytest.raises(PredictAPIException) as error:
            await client.tokens_predict("hello")
    finally:
        await client.aclose()

    assert error.value.code == 400
    assert error.value.detail == "invalid query"


@pytest.mark.asyncio
async def test_predict_512_maps_to_a_retriable_predict_error():
    client = AsyncNuaClient.internal("http://predict", kbid="kb-1")
    try:
        with pytest.raises(RetriablePredictAPIException) as error:
            client._raise_for_response(
                httpx.Response(512, json={"detail": "provider unavailable"}),
                PredictAPIException,
            )
    finally:
        await client.aclose()

    assert error.value.code == 512
    assert error.value.detail == "provider unavailable"
