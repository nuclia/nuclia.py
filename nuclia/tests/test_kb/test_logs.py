from nuclia.sdk.kb import NucliaKB
from nuclia.tests.fixtures import IS_PROD


def test_logs(testing_config):
    if not IS_PROD:
        assert True
        return
    nkb = NucliaKB()
    logs = nkb.logs.get(type="NEW", month="2024-06")
    assert len(logs) == 23
