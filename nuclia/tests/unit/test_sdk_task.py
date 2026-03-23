"""Tests for NucliaTask/AsyncNucliaTask — injects mock ndb to bypass @kb decorator."""
import json
from unittest.mock import AsyncMock, MagicMock

import pytest
from nuclia_models.worker.tasks import (
    ApplyOptions,
    JobStatus,
    PublicTaskSet,
    TaskList,
    TaskName,
    TaskResponse,
)

from nuclia.exceptions import InvalidPayload
from nuclia.sdk.task import AsyncNucliaTask, NucliaTask


def _mock_response(data: dict) -> MagicMock:
    resp = MagicMock()
    resp.json.return_value = data
    return resp


def _task_response_dict():
    return {"name": "dummy", "status": "running", "id": "task-1"}


def _task_list_dict():
    return {"tasks": [], "running": [], "configs": [], "done": []}


def _public_task_set_dict():
    return {"task": {"name": "dummy", "description": "d", "validation": {}}, "id": "t-1", "scheduled_at": None}


# ── NucliaTask (sync) ─────────────────────────────────────────────────────────


def test_task_list():
    ndb = MagicMock()
    ndb.list_tasks.return_value = _mock_response(_task_list_dict())
    result = NucliaTask().list(ndb=ndb)
    assert isinstance(result, TaskList)


def test_task_start_raises_invalid_payload_for_dict_params_without_validation():
    """DUMMY task has no validation model; passing a dict raises InvalidPayload."""
    ndb = MagicMock()
    with pytest.raises(InvalidPayload):
        NucliaTask().start(
            task_name=TaskName.DUMMY,
            apply=ApplyOptions.NEW,
            parameters={},
            ndb=ndb,
        )


def test_task_start_converts_string_task_name_and_apply():
    """Ensure string task_name/apply are coerced to enums before the validation check."""
    ndb = MagicMock()
    with pytest.raises(InvalidPayload):
        NucliaTask().start(
            task_name="dummy",
            apply="new",
            parameters={},
            ndb=ndb,
        )


def test_task_delete():
    ndb = MagicMock()
    ndb.delete_task.return_value = _mock_response({})
    NucliaTask().delete(task_id="task-1", ndb=ndb)
    ndb.delete_task.assert_called_once_with(task_id="task-1", cleanup=False)


def test_task_delete_swallows_invalid_payload():
    ndb = MagicMock()
    ndb.delete_task.side_effect = InvalidPayload("bad")
    # Should not raise
    NucliaTask().delete(task_id="task-1", ndb=ndb)


def test_task_stop():
    ndb = MagicMock()
    ndb.stop_task.return_value = _mock_response(_task_response_dict())
    result = NucliaTask().stop(task_id="task-1", ndb=ndb)
    assert isinstance(result, TaskResponse)


def test_task_get():
    ndb = MagicMock()
    ndb.get_task.return_value = _mock_response(_public_task_set_dict())
    result = NucliaTask().get(task_id="task-1", ndb=ndb)
    assert isinstance(result, PublicTaskSet)


def test_task_restart():
    ndb = MagicMock()
    ndb.restart_task.return_value = _mock_response(_task_response_dict())
    result = NucliaTask().restart(task_id="task-1", ndb=ndb)
    assert isinstance(result, TaskResponse)


# ── AsyncNucliaTask ───────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_async_task_list():
    ndb = AsyncMock()
    ndb.list_tasks.return_value = _mock_response(_task_list_dict())
    result = await AsyncNucliaTask().list(ndb=ndb)
    assert isinstance(result, TaskList)


@pytest.mark.asyncio
async def test_async_task_start_raises_invalid_payload():
    """DUMMY task has no validation model; passing a dict raises InvalidPayload."""
    ndb = AsyncMock()
    with pytest.raises(InvalidPayload):
        await AsyncNucliaTask().start(
            task_name=TaskName.DUMMY,
            apply=ApplyOptions.NEW,
            parameters={},
            ndb=ndb,
        )


@pytest.mark.asyncio
async def test_async_task_stop():
    ndb = AsyncMock()
    ndb.stop_task.return_value = _mock_response(_task_response_dict())
    result = await AsyncNucliaTask().stop(task_id="task-1", ndb=ndb)
    assert isinstance(result, TaskResponse)


@pytest.mark.asyncio
async def test_async_task_get():
    ndb = AsyncMock()
    ndb.get_task.return_value = _mock_response(_public_task_set_dict())
    result = await AsyncNucliaTask().get(task_id="task-1", ndb=ndb)
    assert isinstance(result, PublicTaskSet)


@pytest.mark.asyncio
async def test_async_task_restart():
    ndb = AsyncMock()
    ndb.restart_task.return_value = _mock_response(_task_response_dict())
    result = await AsyncNucliaTask().restart(task_id="task-1", ndb=ndb)
    assert isinstance(result, TaskResponse)


@pytest.mark.asyncio
async def test_async_task_delete():
    ndb = AsyncMock()
    ndb.delete_task.return_value = _mock_response({})
    await AsyncNucliaTask().delete(task_id="task-1", ndb=ndb)
    ndb.delete_task.assert_called_once_with(task_id="task-1", cleanup=False)
