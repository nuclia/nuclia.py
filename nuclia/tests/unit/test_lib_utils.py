import json
import logging
import pytest
from unittest.mock import MagicMock, patch

import httpx
import requests

from nuclia.exceptions import (
    DuplicateError,
    InvalidPayload,
    RateLimitError,
    UserTokenExpired,
)
from nuclia.lib.utils import (
    _raise_for_status,
    build_httpx_async_client,
    build_httpx_client,
    handle_http_sync_errors,
    serialize,
)


# --- _raise_for_status ---


def test_raise_for_status_403_token_expired():
    response = MagicMock(spec=httpx.Response)
    with pytest.raises(UserTokenExpired):
        _raise_for_status(
            403,
            "Hydra token is either unexistent or revoked",
            response=response,
        )


def test_raise_for_status_429_rate_limit():
    with pytest.raises(RateLimitError):
        _raise_for_status(429, "too many requests")


def test_raise_for_status_409_duplicate():
    with pytest.raises(DuplicateError):
        _raise_for_status(409, "conflict")


def test_raise_for_status_422_invalid_payload():
    with pytest.raises(InvalidPayload):
        _raise_for_status(422, "bad input")


def test_raise_for_status_400_httpx_response():
    mock_request = MagicMock()
    mock_response = MagicMock(spec=httpx.Response)
    with pytest.raises(httpx.HTTPStatusError):
        _raise_for_status(400, "bad request", response=mock_response, request=mock_request)


def test_raise_for_status_500_requests_response():
    mock_response = MagicMock(spec=requests.Response)
    with pytest.raises(requests.HTTPError):
        _raise_for_status(500, "server error", response=mock_response)


def test_raise_for_status_generic_error_no_response():
    with pytest.raises(Exception, match="Status code 503"):
        _raise_for_status(503, "unavailable")


def test_raise_for_status_200_does_not_raise():
    # Should not raise for 2xx
    _raise_for_status(200, "ok")


def test_raise_for_status_403_not_token_error():
    # 403 without the specific message should raise HTTPStatusError (if httpx response)
    mock_request = MagicMock()
    mock_response = MagicMock(spec=httpx.Response)
    with pytest.raises(httpx.HTTPStatusError):
        _raise_for_status(403, "Forbidden", response=mock_response, request=mock_request)


# --- handle_http_sync_errors ---


def test_handle_http_sync_errors_ok_response():
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.text = "ok"
    # Should not raise
    handle_http_sync_errors(mock_response)


def test_handle_http_sync_errors_rate_limit():
    mock_response = MagicMock()
    mock_response.status_code = 429
    mock_response.text = "too many requests"
    with pytest.raises(RateLimitError):
        handle_http_sync_errors(mock_response)


# --- serialize ---


def test_serialize_none_returns_none():
    result = serialize(None)
    assert result is None


def test_serialize_string_returns_string():
    result = serialize("hello")
    assert result == "hello"


def test_serialize_resource_list():
    from nucliadb_models.resource import Resource, ResourceList, ResourcePagination

    resource = Resource(id="res-1", icon="text/plain", title="My Resource", slug="my-resource")
    pagination = ResourcePagination(page=0, size=20, last=True)
    resource_list = ResourceList(resources=[resource], pagination=pagination)
    result = serialize(resource_list)
    assert "res-1" in result
    assert "My Resource" in result


def test_serialize_knowledge_box_list():
    from nucliadb_models.resource import KnowledgeBoxList, KnowledgeBoxObjSummary

    kb = KnowledgeBoxObjSummary(uuid="kb-uuid", slug="my-kb")
    kb_list = KnowledgeBoxList(kbs=[kb])
    result = serialize(kb_list)
    assert "kb-uuid" in result
    assert "my-kb" in result


def test_serialize_task_definition():
    from nuclia_models.worker.tasks import TaskDefinition, TaskName

    task = TaskDefinition(
        name=list(TaskName)[0],
        description="Test task",
        validation={"key": "value"},
    )
    result = serialize(task)
    # Should be JSON
    parsed = json.loads(result)
    assert "key" in parsed


def test_serialize_task_list():
    from nuclia_models.worker.tasks import TaskDefinition, TaskList, TaskName

    task = TaskDefinition(name=list(TaskName)[0], description="Test task", validation={})
    task_list = TaskList(tasks=[task], running=[], configs=[], done=[])
    result = serialize(task_list)
    assert "Available tasks" in result


def test_serialize_arag_answer():
    from nuclia_models.agent.interaction import AragAnswer, AnswerOperation

    answer = AragAnswer(operation=AnswerOperation.ANSWER, answer="42")
    result = serialize(answer)
    parsed = json.loads(result)
    assert "answer" in parsed
    assert parsed["operation"] == "ANSWER"


def test_serialize_sync_ask_response_success():
    from nucliadb_models.search import KnowledgeboxFindResults, SyncAskResponse

    retrieval = KnowledgeboxFindResults(
        resources={}, query="q", total=0, page_number=0, page_size=0, relations=None
    )
    response = SyncAskResponse(
        status="success",
        answer="hello world",
        retrieval_results=retrieval,
    )
    result = serialize(response)
    assert "hello world" in result


def test_serialize_sync_ask_response_error():
    from nucliadb_models.search import KnowledgeboxFindResults, SyncAskResponse

    retrieval = KnowledgeboxFindResults(
        resources={}, query="q", total=0, page_number=0, page_size=0, relations=None
    )
    response = SyncAskResponse(
        status="error",
        answer="",
        error_details="Something went wrong",
        retrieval_results=retrieval,
    )
    result = serialize(response)
    assert "ERROR" in result
    assert "Something went wrong" in result


def test_serialize_generator():
    def gen():
        yield "item1"
        yield "item2"

    result = serialize(gen())
    # Generator items should be printed, result is empty string
    assert result == ""


# --- build_httpx_client ---


def test_build_httpx_client_returns_client():
    client = build_httpx_client()
    assert isinstance(client, httpx.Client)


def test_build_httpx_client_includes_user_agent():
    client = build_httpx_client()
    assert "User-Agent" in client.headers
    assert "nuclia" in client.headers["User-Agent"]


def test_build_httpx_client_with_extra_headers():
    client = build_httpx_client(headers={"X-Custom": "value"})
    assert client.headers.get("X-Custom") == "value"


def test_build_httpx_client_with_base_url():
    client = build_httpx_client(base_url="https://example.com")
    assert "example.com" in str(client.base_url)


def test_build_httpx_async_client_returns_async_client():
    client = build_httpx_async_client()
    assert isinstance(client, httpx.AsyncClient)


def test_build_httpx_async_client_includes_user_agent():
    client = build_httpx_async_client()
    assert "User-Agent" in client.headers
    assert "nuclia" in client.headers["User-Agent"]
