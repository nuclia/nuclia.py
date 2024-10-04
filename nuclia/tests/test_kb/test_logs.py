from nuclia.sdk.kb import NucliaKB
from nuclia.tests.fixtures import IS_PROD
from nuclia.lib.kb import LogType


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
    nkb = NucliaKB()
    logs = nkb.logs.get(type=LogType.NEW, month="2024-06")
    assert len(logs) == 23
