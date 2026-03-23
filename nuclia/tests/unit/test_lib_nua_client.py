"""Tests for NuaClient using respx to mock httpx calls."""
import pytest
import httpx
import respx

from nuclia.lib.nua import NuaClient
from nuclia.lib.nua_responses import (
    Sentence,
    Tokens,
    QueryInfo,
)
from nuclia.exceptions import NuaAPIException

BASE_URL = "https://europe-1.rag.progress.cloud"
TOKEN = "test-token"


def make_client() -> NuaClient:
    return NuaClient(region="europe-1", account="acc", token=TOKEN)


# ── _request ──────────────────────────────────────────────────────────────────


def test_request_raises_nua_api_exception_on_error():
    client = make_client()
    with respx.mock(base_url=BASE_URL) as mock:
        mock.get("/api/v1/predict/sentence").mock(
            return_value=httpx.Response(500, text="Internal Server Error")
        )
        with pytest.raises(NuaAPIException) as exc_info:
            client.sentence_predict("hello")
        assert exc_info.value.code == 500


# ── sentence_predict ──────────────────────────────────────────────────────────


def test_sentence_predict():
    client = make_client()
    with respx.mock(base_url=BASE_URL) as mock:
        mock.get("/api/v1/predict/sentence").mock(
            return_value=httpx.Response(200, json={"data": [0.1, 0.2, 0.3], "time": 0.05})
        )
        result = client.sentence_predict("hello world")
    assert isinstance(result, Sentence)
    assert result.data == [0.1, 0.2, 0.3]


def test_sentence_predict_with_model():
    client = make_client()
    with respx.mock(base_url=BASE_URL) as mock:
        route = mock.get("/api/v1/predict/sentence").mock(
            return_value=httpx.Response(200, json={"data": [0.5], "time": 0.01})
        )
        result = client.sentence_predict("hello", model="my-model")
    assert result.data == [0.5]
    assert "my-model" in str(route.calls[0].request.url)


# ── tokens_predict ────────────────────────────────────────────────────────────


def test_tokens_predict():
    client = make_client()
    with respx.mock(base_url=BASE_URL) as mock:
        mock.get("/api/v1/predict/tokens").mock(
            return_value=httpx.Response(
                200,
                json={"tokens": [{"text": "hello", "ner": "NOUN", "start": 0, "end": 5}], "time": 0.01},
            )
        )
        result = client.tokens_predict("hello world")
    assert isinstance(result, Tokens)


# ── query_predict ─────────────────────────────────────────────────────────────


def test_query_predict():
    client = make_client()
    with respx.mock(base_url=BASE_URL) as mock:
        mock.get("/api/v1/predict/query").mock(
            return_value=httpx.Response(
                200,
                json={
                    "language": "en",
                    "stop_words": [],
                    "semantic_threshold": 0.5,
                    "visual_llm": False,
                    "max_context": 1000,
                    "entities": {"tokens": [], "time": 0.01},
                    "sentence": {"data": [0.1], "time": 0.01},
                },
            )
        )
        result = client.query_predict("what is nuclia")
    assert isinstance(result, QueryInfo)
    assert result.language == "en"


def test_query_predict_with_models():
    client = make_client()
    with respx.mock(base_url=BASE_URL) as mock:
        route = mock.get("/api/v1/predict/query").mock(
            return_value=httpx.Response(
                200,
                json={
                    "language": "en",
                    "stop_words": [],
                    "semantic_threshold": 0.5,
                    "visual_llm": False,
                    "max_context": 1000,
                    "entities": {"tokens": [], "time": 0.01},
                    "sentence": {"data": [0.1], "time": 0.01},
                },
            )
        )
        result = client.query_predict(
            "test", semantic_model="sm", token_model="tm", generative_model="gm"
        )
    url_str = str(route.calls[0].request.url)
    assert "semantic_model=sm" in url_str
    assert "token_model=tm" in url_str
    assert "generative_model=gm" in url_str


# ── processing_status ─────────────────────────────────────────────────────────


def test_processing_status():
    from nuclia.lib.nua_responses import ProcessRequestStatusResults
    client = make_client()
    with respx.mock(base_url=BASE_URL) as mock:
        mock.get("/api/v2/processing/status").mock(
            return_value=httpx.Response(
                200, json={"results": [], "cursor": None}
            )
        )
        result = client.processing_status()
    assert isinstance(result, ProcessRequestStatusResults)


# ── rerank ────────────────────────────────────────────────────────────────────


def test_rerank():
    from nuclia.lib.nua_responses import RerankResponse
    from nuclia.lib.nua import RerankModel
    client = make_client()
    model = RerankModel(question="test", user_id="user1", context={"0": "some text"})
    with respx.mock(base_url=BASE_URL) as mock:
        mock.post("/api/v1/predict/rerank").mock(
            return_value=httpx.Response(200, json={"context_scores": {"0": 0.9}})
        )
        result = client.rerank(model=model)
    assert isinstance(result, RerankResponse)
    assert result.context_scores == {"0": 0.9}


# ── AsyncNuaClient ────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_async_sentence_predict():
    from nuclia.lib.nua import AsyncNuaClient
    async_client = AsyncNuaClient(region="europe-1", account="acc", token=TOKEN)
    with respx.mock(base_url=BASE_URL) as mock:
        mock.get("/api/v1/predict/sentence").mock(
            return_value=httpx.Response(200, json={"data": [0.9, 0.8], "time": 0.02})
        )
        result = await async_client.sentence_predict("async test")
    assert isinstance(result, Sentence)
    assert result.data == [0.9, 0.8]


@pytest.mark.asyncio
async def test_async_tokens_predict():
    from nuclia.lib.nua import AsyncNuaClient
    async_client = AsyncNuaClient(region="europe-1", account="acc", token=TOKEN)
    with respx.mock(base_url=BASE_URL) as mock:
        mock.get("/api/v1/predict/tokens").mock(
            return_value=httpx.Response(
                200, json={"tokens": [{"text": "a", "ner": "NOUN", "start": 0, "end": 1}], "time": 0.01}
            )
        )
        result = await async_client.tokens_predict("test")
    assert isinstance(result, Tokens)


@pytest.mark.asyncio
async def test_async_request_raises_on_error():
    from nuclia.lib.nua import AsyncNuaClient
    async_client = AsyncNuaClient(region="europe-1", account="acc", token=TOKEN)
    with respx.mock(base_url=BASE_URL) as mock:
        mock.get("/api/v1/predict/sentence").mock(
            return_value=httpx.Response(401, text="Unauthorized")
        )
        with pytest.raises(NuaAPIException) as exc_info:
            await async_client.sentence_predict("fail")
        assert exc_info.value.code == 401
