from nuclia.sdk.kb import NucliaKB
from nuclia.tests.fixtures import IS_PROD
from nuclia.lib.kb import LogType
from nuclia.lib.models import ActivityLogsQuery, Pagination


def test_logs(testing_config):
    if not IS_PROD:
        assert True
        return
    nkb = NucliaKB()
    logs = nkb.logs.get(type=LogType.NEW, month="2024-06")
    assert len(logs) == 23


def test_activity_logs_query(testing_config):
    if not IS_PROD:
        assert True
        return
    query = ActivityLogsQuery(
        year_month="2024-10",
        show=["id", "date", "question", "answer"],
        filters={},
        pagination=Pagination(limit=10),
    )
    nkb = NucliaKB()
    output = nkb.logs.query(type=LogType.CHAT, query=query)
    assert len(output.data) == 10
    assert output.has_more
