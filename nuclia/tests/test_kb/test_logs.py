import pytest
from nuclia_models.events.activity_logs import (
    ActivityLogsQuery,
    DownloadActivityLogsQuery,
    DownloadFormat,
    EventType,
    Pagination,
)

from nuclia.sdk.kb import AsyncNucliaKB, NucliaKB
from nuclia.tests.fixtures import IS_PROD


def test_activity_logs_query(testing_config):
    if not IS_PROD:
        assert True
        return
    query = ActivityLogsQuery(
        year_month="2024-10",
        show=["id", "date", "client_type", "total_duration"],
        filters={},
        pagination=Pagination(limit=10),
    )
    nkb = NucliaKB()
    output = nkb.logs.query(type=EventType.CHAT, query=query)
    assert len(output.data) == 10
    assert output.has_more


def test_activity_logs_download(testing_config):
    if not IS_PROD:
        assert True
        return
    query = DownloadActivityLogsQuery(
        year_month="2024-10",
        show=["id", "date", "client_type", "total_duration"],
        filters={},
    )
    nkb = NucliaKB()
    output = nkb.logs.download(
        type=EventType.CHAT, query=query, download_format=DownloadFormat.NDJSON
    )
    assert output.request_id
    assert output.download_url is None


@pytest.mark.asyncio
async def test_activity_logs_query_async(testing_config):
    if not IS_PROD:
        assert True
        return
    query = ActivityLogsQuery(
        year_month="2024-10",
        show=["id", "date", "client_type", "total_duration"],
        filters={},
        pagination=Pagination(limit=10),
    )
    nkb = AsyncNucliaKB()
    output = await nkb.logs.query(type=EventType.CHAT, query=query)
    assert len(output.data) == 10
    assert output.has_more


@pytest.mark.asyncio
async def test_activity_logs_download_async(testing_config):
    if not IS_PROD:
        assert True
        return
    query = DownloadActivityLogsQuery(
        year_month="2024-10",
        show=["id", "date", "client_type", "total_duration"],
        filters={},
    )
    nkb = AsyncNucliaKB()
    output = await nkb.logs.download(
        type=EventType.CHAT, query=query, download_format=DownloadFormat.NDJSON
    )
    assert output.request_id
    assert output.download_url is None


def test_activity_logs_ask_query(testing_config):
    if not IS_PROD:
        assert True
        return
    query = ActivityLogsQuery(
        year_month="2024-10",
        show=["id", "date", "client_type", "total_duration"],
        filters={},
        pagination=Pagination(limit=10),
    )
    nkb = NucliaKB()
    output = nkb.logs.query(type=EventType.ASK, query=query)
    assert len(output.data) == 10
    assert output.has_more


@pytest.mark.asyncio
async def test_activity_logs_ask_download_async(testing_config):
    if not IS_PROD:
        assert True
        return
    query = DownloadActivityLogsQuery(
        year_month="2024-10",
        show=["id", "date", "client_type", "total_duration"],
        filters={},
    )
    nkb = AsyncNucliaKB()
    output = await nkb.logs.download(
        type=EventType.ASK, query=query, download_format=DownloadFormat.NDJSON
    )
    assert output.request_id
    assert output.download_url is None
