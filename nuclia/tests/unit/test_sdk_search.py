"""Tests for NucliaSearch using MagicMock ndb injection."""
import pytest
from unittest.mock import MagicMock

from nucliadb_models.search import (
    KnowledgeboxSearchResults,
    KnowledgeboxFindResults,
)
from nucliadb_sdk.v2.sdk import SyncAskResponse

from nuclia.sdk.search import NucliaSearch, AskAnswer


def make_mock_ndb(kbid: str = "test-kb") -> MagicMock:
    mock = MagicMock()
    mock.kbid = kbid
    return mock


# ── AskAnswer ─────────────────────────────────────────────────────────────────


def test_ask_answer_str_with_answer():
    aa = AskAnswer.__new__(AskAnswer)
    aa.answer = b"The answer is 42"
    aa.object = None
    assert str(aa) == "The answer is 42"


def test_ask_answer_str_with_object():
    import json
    aa = AskAnswer.__new__(AskAnswer)
    aa.answer = b""
    aa.object = {"result": "value"}
    assert str(aa) == json.dumps({"result": "value"})


def test_ask_answer_str_empty():
    aa = AskAnswer.__new__(AskAnswer)
    aa.answer = b""
    aa.object = None
    assert str(aa) == ""


# ── NucliaSearch.search ────────────────────────────────────────────────────────


def test_search_with_str_query():
    sdk = NucliaSearch()
    ndb = make_mock_ndb()
    ndb.ndb.search.return_value = KnowledgeboxSearchResults()
    result = sdk.search(query="hello world", ndb=ndb)
    ndb.ndb.search.assert_called_once()
    call_args = ndb.ndb.search.call_args
    assert call_args[1]["kbid"] == "test-kb"


def test_search_with_dict_query():
    from nucliadb_models.search import SearchRequest
    sdk = NucliaSearch()
    ndb = make_mock_ndb()
    ndb.ndb.search.return_value = KnowledgeboxSearchResults()
    result = sdk.search(query={"query": "test"}, ndb=ndb)
    ndb.ndb.search.assert_called_once()


def test_search_with_request_object():
    from nucliadb_models.search import SearchRequest
    sdk = NucliaSearch()
    ndb = make_mock_ndb()
    ndb.ndb.search.return_value = KnowledgeboxSearchResults()
    req = SearchRequest(query="my query")
    result = sdk.search(query=req, ndb=ndb)
    ndb.ndb.search.assert_called_once()
    assert ndb.ndb.search.call_args[0][0] is req


def test_search_with_invalid_type_raises():
    sdk = NucliaSearch()
    ndb = make_mock_ndb()
    with pytest.raises(TypeError):
        sdk.search(query=12345, ndb=ndb)


# ── NucliaSearch.find ─────────────────────────────────────────────────────────


def test_find_with_str_query():
    sdk = NucliaSearch()
    ndb = make_mock_ndb()
    ndb.ndb.find.return_value = KnowledgeboxFindResults(resources={})
    result = sdk.find(query="find something", ndb=ndb)
    ndb.ndb.find.assert_called_once()


def test_find_with_request_object():
    from nucliadb_models.search import FindRequest
    sdk = NucliaSearch()
    ndb = make_mock_ndb()
    ndb.ndb.find.return_value = KnowledgeboxFindResults(resources={})
    req = FindRequest(query="my find")
    result = sdk.find(query=req, ndb=ndb)
    assert ndb.ndb.find.call_args[0][0] is req


def test_find_with_invalid_type_raises():
    sdk = NucliaSearch()
    ndb = make_mock_ndb()
    with pytest.raises(TypeError):
        sdk.find(query=12345, ndb=ndb)


# ── NucliaSearch.catalog ──────────────────────────────────────────────────────


def test_catalog_with_str_query():
    sdk = NucliaSearch()
    ndb = make_mock_ndb()
    ndb.ndb.catalog.return_value = MagicMock()
    result = sdk.catalog(query="hello", ndb=ndb)
    ndb.ndb.catalog.assert_called_once()


def test_catalog_with_invalid_type_raises():
    sdk = NucliaSearch()
    ndb = make_mock_ndb()
    with pytest.raises(TypeError):
        sdk.catalog(query=99, ndb=ndb)


# ── NucliaSearch.ask ──────────────────────────────────────────────────────────


def _make_ask_response(answer: str = "42") -> SyncAskResponse:
    return SyncAskResponse(
        answer=answer,
        status="success",
        retrieval_results=KnowledgeboxFindResults(resources={}),
    )


def test_ask_with_str_query():
    sdk = NucliaSearch()
    ndb = make_mock_ndb()
    ndb.ndb.ask.return_value = _make_ask_response("The answer is 42")
    result = sdk.ask(query="what is the answer?", ndb=ndb)
    assert isinstance(result, AskAnswer)
    assert result.answer == b"The answer is 42"
    assert str(result) == "The answer is 42"


def test_ask_with_dict_query():
    sdk = NucliaSearch()
    ndb = make_mock_ndb()
    ndb.ndb.ask.return_value = _make_ask_response("hello")
    result = sdk.ask(query={"query": "test question"}, ndb=ndb)
    assert isinstance(result, AskAnswer)


def test_ask_with_request_object():
    from nucliadb_models.search import AskRequest
    sdk = NucliaSearch()
    ndb = make_mock_ndb()
    ndb.ndb.ask.return_value = _make_ask_response()
    req = AskRequest(query="test")
    result = sdk.ask(query=req, ndb=ndb)
    assert isinstance(result, AskAnswer)


def test_ask_with_invalid_type_raises():
    sdk = NucliaSearch()
    ndb = make_mock_ndb()
    with pytest.raises(TypeError):
        sdk.ask(query=12345, ndb=ndb)


# ── Async NucliaSearch ────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_async_search():
    from unittest.mock import AsyncMock
    from nuclia.sdk.search import AsyncNucliaSearch
    sdk = AsyncNucliaSearch()
    ndb = make_mock_ndb()
    ndb.ndb.search = AsyncMock(return_value=KnowledgeboxSearchResults())
    result = await sdk.search(query="async hello", ndb=ndb)
    ndb.ndb.search.assert_called_once()


@pytest.mark.asyncio
async def test_async_find():
    from unittest.mock import AsyncMock
    from nuclia.sdk.search import AsyncNucliaSearch
    sdk = AsyncNucliaSearch()
    ndb = make_mock_ndb()
    ndb.ndb.find = AsyncMock(return_value=KnowledgeboxFindResults(resources={}))
    result = await sdk.find(query="async find", ndb=ndb)
    ndb.ndb.find.assert_called_once()
