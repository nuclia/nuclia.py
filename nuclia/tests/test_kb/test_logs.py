from nuclia.sdk.kb import NucliaKB
from nuclia.tests.fixtures import IS_PROD


def test_logs(testing_config):
    if not IS_PROD:
        assert True
        return
    nkb = NucliaKB()
    logs = nkb.logs.get(type="SEARCH", month="2023-06")
    assert len(logs) == 1
