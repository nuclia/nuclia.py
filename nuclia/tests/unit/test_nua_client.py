import json

import httpx
import pytest
from nuclia_models.predict.generative_responses import TextGenerativeResponse

from nuclia.exceptions import PredictAPIException, PredictLimitsExceededError
from nuclia.lib.nua import (
    NuaClient,
    NuaKeyMissingError,
    QueryRequest,
    RephraseRequest,
)
from nuclia.lib.nua_responses import ChatModel, QueryInfo, RephraseModel, RerankModel


def chunk(chunk_type: str, **data) -> str:
    return json.dumps({"chunk": {"type": chunk_type, **data}}) + "\n"


def close_client(client: NuaClient) -> None:
    client.close()


def test_internal_query_predict_uses_kbid_headers():
    requests = []

    def handler(request: httpx.Request) -> httpx.Response:
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

    client = NuaClient.internal("http://predict", kbid="kb-1", account="account-1")
    client.client = httpx.Client(transport=httpx.MockTransport(handler))
    try:
        result = client.query_predict(QueryRequest(text="hello"))
    finally:
        close_client(client)

    assert result.query == "hello"
    assert requests[0].url == "http://predict/api/internal/predict/query"
    assert requests[0].headers["x-stf-kbid"] == "kb-1"
    assert requests[0].headers["x-stf-account"] == "account-1"
    assert requests[0].method == "POST"


def test_legacy_query_predict_uses_get_response_model():
    def handler(request: httpx.Request) -> httpx.Response:
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

    client = NuaClient("http://predict", account="")
    client.client = httpx.Client(transport=httpx.MockTransport(handler))
    try:
        result = client.query_predict("hello")
    finally:
        close_client(client)

    assert isinstance(result, QueryInfo)


def test_legacy_rephrase_uses_root_response_model():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url == "http://predict/api/v1/predict/rephrase?model=model-1"
        return httpx.Response(200, json="new query")

    client = NuaClient("http://predict", account="")
    client.client = httpx.Client(transport=httpx.MockTransport(handler))
    try:
        result = client.rephrase("old", model="model-1")
    finally:
        close_client(client)

    assert isinstance(result, RephraseModel)
    assert result.root == "new query"


def test_legacy_generate_stream_returns_iterator():
    client = NuaClient("http://predict", account="")
    client.stream_client = httpx.Client(
        transport=httpx.MockTransport(
            lambda _: httpx.Response(200, content=chunk("text", text="hello"))
        )
    )
    try:
        chunks = list(
            client.generate_stream(ChatModel(question="hello", user_id="user"))
        )
    finally:
        close_client(client)

    assert isinstance(chunks[0].chunk, TextGenerativeResponse)


def test_onprem_generate_stream_returns_headers_and_chunks():
    def handler(request: httpx.Request) -> httpx.Response:
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

    client = NuaClient.onprem(
        "http://predict", service_account="service-account", kbid="kb-1"
    )
    client.stream_client = httpx.Client(transport=httpx.MockTransport(handler))
    try:
        response = client.generate_stream(
            ChatModel(question="hello", user_id="user"), return_metadata=True
        )
        chunks = list(response.stream)
    finally:
        close_client(client)

    assert response.learning_id == "learning-1"
    assert response.model == "model-1"
    assert isinstance(chunks[0].chunk, TextGenerativeResponse)
    assert chunks[0].chunk.text == "hello"


def test_onprem_rephrase_parses_headers():
    def handler(request: httpx.Request) -> httpx.Response:
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

    client = NuaClient.onprem(
        "http://predict", kbid="kb-1", service_account="service-account"
    )
    client.client = httpx.Client(transport=httpx.MockTransport(handler))
    try:
        result = client.rephrase(RephraseRequest(question="old", user_id="user"))
    finally:
        close_client(client)

    assert result.root == "new query"
    assert result.use_chat_history is False
    assert result.learning_id == "learning-2"
    assert result.model == "model-2"


def test_onprem_rephrase_without_kbid_uses_base_endpoint():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url == "http://predict/api/v1/predict/rephrase"
        return httpx.Response(200, json="new query")

    client = NuaClient.onprem("http://predict", service_account="service-account")
    client.client = httpx.Client(transport=httpx.MockTransport(handler))
    try:
        result = client.rephrase(RephraseRequest(question="old"))
    finally:
        close_client(client)

    assert result.root == "new query"


def test_internal_rerank_uses_request_headers():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url == "http://predict/api/internal/predict/rerank"
        assert request.headers["x-stf-kbid"] == "kb-1"
        return httpx.Response(200, json={"context_scores": {"1": 0.9}})

    client = NuaClient.internal("http://predict", kbid="kb-1")
    client.client = httpx.Client(transport=httpx.MockTransport(handler))
    try:
        result = client.rerank(
            RerankModel(question="hello", user_id="user", context={"1": "text"})
        )
    finally:
        close_client(client)

    assert result.context_scores == {"1": 0.9}


def test_onprem_rerank_without_kbid_uses_base_endpoint():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url == "http://predict/api/v1/predict/rerank"
        return httpx.Response(200, json={"context_scores": {"1": 0.9}})

    client = NuaClient.onprem("http://predict", service_account="service-account")
    client.client = httpx.Client(transport=httpx.MockTransport(handler))
    try:
        result = client.rerank(
            RerankModel(question="hello", user_id="user", context={"1": "text"})
        )
    finally:
        close_client(client)

    assert result.context_scores == {"1": 0.9}


def test_onprem_predict_requires_service_account():
    client = NuaClient.onprem("http://predict")
    try:
        with pytest.raises(NuaKeyMissingError):
            client.ner_predict("hello")
    finally:
        close_client(client)

    requests = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, json={"tokens": [], "time": 0})

    client = NuaClient.onprem("http://predict", service_account="service-account")
    client.client = httpx.Client(transport=httpx.MockTransport(handler))
    try:
        result = client.ner_predict("hello")
    finally:
        close_client(client)

    assert result.tokens == []
    assert requests[0].url == "http://predict/api/v1/predict/tokens?text=hello"


def test_predict_limits_error_is_typed_and_includes_api_detail():
    client = NuaClient.internal("http://predict", kbid="kb-1")
    client.client = httpx.Client(
        transport=httpx.MockTransport(
            lambda _: httpx.Response(402, json={"detail": "monthly limit reached"})
        )
    )
    try:
        with pytest.raises(PredictLimitsExceededError) as error:
            client.ner_predict("hello")
    finally:
        close_client(client)

    assert error.value.code == 402
    assert error.value.detail == "monthly limit reached"


def test_predict_errors_are_typed_and_include_plain_text_detail():
    client = NuaClient.internal("http://predict", kbid="kb-1")
    client.client = httpx.Client(
        transport=httpx.MockTransport(
            lambda _: httpx.Response(400, text="invalid query")
        )
    )
    try:
        with pytest.raises(PredictAPIException) as error:
            client.ner_predict("hello")
    finally:
        close_client(client)

    assert error.value.code == 400
    assert error.value.detail == "invalid query"
