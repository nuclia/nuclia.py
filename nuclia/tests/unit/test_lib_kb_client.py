"""Tests for NucliaDBClient using respx to mock httpx calls."""
import pytest
import httpx
import respx

from nuclia.lib.kb import (
    NucliaDBClient,
    Environment,
    TaskStartKB,
)
from nuclia.sdk.task import TaskName
from nuclia.exceptions import RaoAPIException

KB_URL = "https://europe-1.rag.progress.cloud/api/v1/kb/kb-test-id"
OSS_URL = "http://localhost:8080/api/v1/kb/test-kb"


def make_cloud_client() -> NucliaDBClient:
    return NucliaDBClient(
        environment=Environment.CLOUD,
        url=KB_URL,
        api_key="test-key",
        region="europe-1",
    )


def make_oss_client() -> NucliaDBClient:
    return NucliaDBClient(environment=Environment.OSS, url=OSS_URL, api_key="key")


# ── init / environment ────────────────────────────────────────────────────────


def test_cloud_client_init():
    client = make_cloud_client()
    assert client.url == KB_URL
    assert client.reader_session is not None
    assert client.writer_session is not None


def test_oss_client_init():
    client = make_oss_client()
    assert client.url == OSS_URL
    assert client.reader_session is not None


def test_cloud_requires_region():
    with pytest.raises(Exception, match="region"):
        NucliaDBClient(
            environment=Environment.CLOUD,
            url=KB_URL,
            api_key="key",
            region=None,
        )


# ── list_tasks ────────────────────────────────────────────────────────────────


def test_list_tasks():
    client = make_cloud_client()
    payload = {"tasks": [], "running": [], "configs": [], "done": []}
    with respx.mock(base_url=KB_URL + "/") as mock:
        mock.get("tasks").mock(return_value=httpx.Response(200, json=payload))
        resp = client.list_tasks()
    assert resp.status_code == 200
    assert resp.json() == payload


def test_list_tasks_raises_on_error():
    from nuclia.lib.utils import HTTPStatusError
    client = make_cloud_client()
    with respx.mock(base_url=KB_URL + "/") as mock:
        mock.get("tasks").mock(return_value=httpx.Response(403, text="Forbidden"))
        with pytest.raises(HTTPStatusError):
            client.list_tasks()


def test_list_tasks_no_session_raises():
    client = NucliaDBClient.__new__(NucliaDBClient)
    client.reader_session = None
    client.writer_session = None
    with pytest.raises(Exception):
        client.list_tasks()


# ── start_task ────────────────────────────────────────────────────────────────


def test_start_task():
    client = make_cloud_client()
    task = TaskStartKB(name=TaskName.DUMMY, parameters=None)
    with respx.mock(base_url=KB_URL + "/") as mock:
        mock.post("task/start").mock(
            return_value=httpx.Response(200, json={"task_id": "task-1"})
        )
        resp = client.start_task(task)
    assert resp.status_code == 200


# ── stop_task ─────────────────────────────────────────────────────────────────


def test_stop_task():
    client = make_cloud_client()
    with respx.mock(base_url=KB_URL + "/") as mock:
        mock.post("task/task-1/stop").mock(return_value=httpx.Response(200, json={}))
        resp = client.stop_task("task-1")
    assert resp.status_code == 200


# ── get_task ──────────────────────────────────────────────────────────────────


def test_get_task():
    client = make_cloud_client()
    with respx.mock(base_url=KB_URL + "/") as mock:
        mock.get("task/task-1/inspect").mock(
            return_value=httpx.Response(200, json={"id": "task-1", "status": "done"})
        )
        resp = client.get_task("task-1")
    assert resp.status_code == 200


# ── delete_task ───────────────────────────────────────────────────────────────


def test_delete_task():
    client = make_cloud_client()
    with respx.mock(base_url=KB_URL + "/") as mock:
        mock.delete("task/task-1").mock(return_value=httpx.Response(200, json={}))
        resp = client.delete_task("task-1")
    assert resp.status_code == 200


def test_delete_task_with_cleanup():
    client = make_cloud_client()
    with respx.mock(base_url=KB_URL + "/") as mock:
        route = mock.delete("task/task-1").mock(return_value=httpx.Response(200, json={}))
        client.delete_task("task-1", cleanup=True)
    assert "cleanup=true" in str(route.calls[0].request.url)


# ── restart_task ──────────────────────────────────────────────────────────────


def test_restart_task():
    client = make_cloud_client()
    with respx.mock(base_url=KB_URL + "/") as mock:
        mock.post("task/task-1/restart").mock(return_value=httpx.Response(200, json={}))
        resp = client.restart_task("task-1")
    assert resp.status_code == 200


# ── extract_strategies ────────────────────────────────────────────────────────


def test_list_extract_strategies():
    client = make_cloud_client()
    with respx.mock(base_url=KB_URL + "/") as mock:
        mock.get("extract_strategies").mock(
            return_value=httpx.Response(200, json={"strategies": []})
        )
        resp = client.list_extract_strategies()
    assert resp.status_code == 200


def test_delete_extract_strategy():
    client = make_cloud_client()
    with respx.mock(base_url=KB_URL + "/") as mock:
        mock.delete("extract_strategies/strategy/strat-1").mock(
            return_value=httpx.Response(200, json={})
        )
        resp = client.delete_extract_strategy("strat-1")
    assert resp.status_code == 200


# ── split_strategies ──────────────────────────────────────────────────────────


def test_list_split_strategies():
    client = make_cloud_client()
    with respx.mock(base_url=KB_URL + "/") as mock:
        mock.get("split_strategies").mock(
            return_value=httpx.Response(200, json={"strategies": []})
        )
        resp = client.list_split_strategies()
    assert resp.status_code == 200


# ── AsyncNucliaDBClient ───────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_async_list_tasks():
    from nuclia.lib.kb import AsyncNucliaDBClient
    client = AsyncNucliaDBClient(
        environment=Environment.CLOUD,
        url=KB_URL,
        api_key="test-key",
        region="europe-1",
    )
    payload = {"tasks": [], "running": [], "configs": [], "done": []}
    with respx.mock(base_url=KB_URL + "/") as mock:
        mock.get("tasks").mock(return_value=httpx.Response(200, json=payload))
        resp = await client.list_tasks()
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_async_start_task():
    from nuclia.lib.kb import AsyncNucliaDBClient
    client = AsyncNucliaDBClient(
        environment=Environment.CLOUD,
        url=KB_URL,
        api_key="test-key",
        region="europe-1",
    )
    task = TaskStartKB(name=TaskName.DUMMY, parameters=None)
    with respx.mock(base_url=KB_URL + "/") as mock:
        mock.post("task/start").mock(return_value=httpx.Response(200, json={"task_id": "x"}))
        resp = await client.start_task(task)
    assert resp.status_code == 200
