from unittest.mock import Mock

import pytest
from nucliadb_models.export_import import Status

from nuclia.sdk.export_import import wait_for_task_to_finish


class FakeStatusResponse:
    def __init__(self, values, total=100, processed=10):
        self.values = values
        self.total = total
        self.processed = processed

    @property
    def status(self):
        return self.values.pop(0)


@pytest.fixture(scope="function")
def ndb_sdk():
    ndb = Mock()
    ndb.export_status = Mock(
        return_value=FakeStatusResponse([Status.RUNNING, Status.FINISHED])
    )
    ndb.import_status = Mock(
        return_value=FakeStatusResponse([Status.RUNNING, Status.FINISHED])
    )
    return ndb


@pytest.fixture(scope="function")
def ndb(ndb_sdk):
    ndb = Mock()
    ndb.ndb = ndb_sdk
    ndb.kbid = "kbid"
    return ndb


def test_wait_for_task_to_finish(ndb):
    wait_for_task_to_finish(ndb, "export", "foo")
    wait_for_task_to_finish(ndb, "import", "foo")
