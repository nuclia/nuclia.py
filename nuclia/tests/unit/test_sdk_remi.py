"""Tests for NucliaRemi/AsyncNucliaRemi — injects mock ndb to bypass @kb decorator."""
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest
from nuclia_models.common.utils import Aggregation
from nuclia_models.events.remi import RemiQuery, RemiQueryResults

from nuclia.sdk.remi import AsyncNucliaRemi, NucliaRemi


def _mock_response(data: dict) -> MagicMock:
    resp = MagicMock()
    resp.json.return_value = data
    return resp


_REMI_RESULTS = {"data": [], "has_more": False}
_REMI_EVENT = {
    "id": 1,
    "question": "q",
    "answer": "a",
    "retrieved_context": [],
    "scores": {},
    "time": "2024-01-01T00:00:00Z",
}
_REMI_SCORES = []


# ── NucliaRemi (sync) ─────────────────────────────────────────────────────────


def test_remi_query_with_object():
    ndb = MagicMock()
    ndb.remi_query.return_value = _mock_response(_REMI_RESULTS)
    query = RemiQuery(month="2024-01")
    result = NucliaRemi().query(query=query, ndb=ndb)
    assert isinstance(result, RemiQueryResults)


def test_remi_query_with_dict():
    ndb = MagicMock()
    ndb.remi_query.return_value = _mock_response(_REMI_RESULTS)
    result = NucliaRemi().query(query={"month": "2024-01"}, ndb=ndb)
    assert isinstance(result, RemiQueryResults)


def test_remi_get_scores_with_datetime():
    ndb = MagicMock()
    ndb.get_remi_scores.return_value = _mock_response(_REMI_SCORES)
    result = NucliaRemi().get_scores(
        starting_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
        to=datetime(2024, 12, 31, tzinfo=timezone.utc),
        aggregation=Aggregation.DAY,
        ndb=ndb,
    )
    assert result == []


def test_remi_get_scores_with_strings():
    ndb = MagicMock()
    ndb.get_remi_scores.return_value = _mock_response(_REMI_SCORES)
    result = NucliaRemi().get_scores(
        starting_at="2024-01-01",
        to="2024-12-31",
        aggregation="DAY",
        ndb=ndb,
    )
    assert result == []


def test_remi_get_scores_no_to():
    ndb = MagicMock()
    ndb.get_remi_scores.return_value = _mock_response(_REMI_SCORES)
    result = NucliaRemi().get_scores(
        starting_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
        to=None,
        aggregation=Aggregation.DAY,
        ndb=ndb,
    )
    assert result == []


# ── AsyncNucliaRemi ───────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_async_remi_query_with_object():
    ndb = AsyncMock()
    ndb.remi_query.return_value = _mock_response(_REMI_RESULTS)
    query = RemiQuery(month="2024-01")
    result = await AsyncNucliaRemi().query(query=query, ndb=ndb)
    assert isinstance(result, RemiQueryResults)


@pytest.mark.asyncio
async def test_async_remi_query_with_dict():
    ndb = AsyncMock()
    ndb.remi_query.return_value = _mock_response(_REMI_RESULTS)
    result = await AsyncNucliaRemi().query(query={"month": "2024-01"}, ndb=ndb)
    assert isinstance(result, RemiQueryResults)


@pytest.mark.asyncio
async def test_async_remi_get_scores():
    ndb = AsyncMock()
    ndb.get_remi_scores.return_value = _mock_response(_REMI_SCORES)
    result = await AsyncNucliaRemi().get_scores(
        starting_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
        to=None,
        aggregation=Aggregation.DAY,
        ndb=ndb,
    )
    assert result == []
