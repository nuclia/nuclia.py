"""Tests for NucliaAgentSessions/AsyncNucliaAgentSessions — injects mock ac."""
from unittest.mock import AsyncMock, MagicMock

import pytest
from nucliadb_models.resource import Resource, ResourceList, ResourcePagination

from nuclia.sdk.agent_sessions import AsyncNucliaAgentSessions, NucliaAgentSessions


def _resource_list():
    pagination = ResourcePagination(page=0, size=20, last=True)
    return ResourceList(resources=[], pagination=pagination)


# ── NucliaAgentSessions (sync) ────────────────────────────────────────────────


def test_sessions_new():
    ac = MagicMock()
    ac.new_session.return_value = "session-uuid"
    result = NucliaAgentSessions().new("my-session", ac=ac)
    assert result == "session-uuid"
    ac.new_session.assert_called_once_with("my-session")


def test_sessions_delete():
    ac = MagicMock()
    NucliaAgentSessions().delete("session-uuid", ac=ac)
    ac.delete_session.assert_called_once_with("session-uuid")


def test_sessions_list():
    ac = MagicMock()
    ac.get_sessions.return_value = _resource_list()
    result = NucliaAgentSessions().list(page=0, page_size=10, ac=ac)
    assert isinstance(result, ResourceList)
    ac.get_sessions.assert_called_once_with(page=0, page_size=10)


def test_sessions_get():
    ac = MagicMock()
    ac.get_session.return_value = Resource(id="res-1")
    result = NucliaAgentSessions().get("session-uuid", ac=ac)
    assert result.id == "res-1"


# ── AsyncNucliaAgentSessions ──────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_async_sessions_new():
    ac = AsyncMock()
    ac.new_session.return_value = "session-uuid"
    result = await AsyncNucliaAgentSessions().new("my-session", ac=ac)
    assert result == "session-uuid"


@pytest.mark.asyncio
async def test_async_sessions_delete():
    ac = AsyncMock()
    await AsyncNucliaAgentSessions().delete("session-uuid", ac=ac)
    ac.delete_session.assert_called_once_with("session-uuid")


@pytest.mark.asyncio
async def test_async_sessions_list():
    ac = AsyncMock()
    ac.get_sessions.return_value = _resource_list()
    result = await AsyncNucliaAgentSessions().list(page=1, page_size=5, ac=ac)
    assert isinstance(result, ResourceList)


@pytest.mark.asyncio
async def test_async_sessions_get():
    ac = AsyncMock()
    ac.get_session.return_value = Resource(id="res-2")
    result = await AsyncNucliaAgentSessions().get("session-uuid", ac=ac)
    assert result.id == "res-2"
