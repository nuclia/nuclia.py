from nuclia.sdk.export_import import wait_for_finished
from unittest.mock import Mock
from nucliadb_models.export_import import Status
import pytest


class StatusResponse:
    def __init__(self, values):
        self.values = values

    @property
    def status(self):
        return self.values.pop(0)


@pytest.fixture(scope="function")
def ndb_sdk():
    ndb = Mock()
    ndb.export_status = Mock(return_value=StatusResponse([Status.RUNNING, Status.FINISHED]))
    ndb.import_status = Mock(return_value=StatusResponse([Status.RUNNING, Status.FINISHED]))
    return ndb


@pytest.fixture(scope="function")
def ndb(ndb_sdk):
    ndb = Mock()
    ndb.ndb = ndb_sdk
    ndb.kbid = "kbid"
    return ndb


def test_wait_for_finished(ndb):
    wait_for_finished(ndb, "export", "foo")
    wait_for_finished(ndb, "import", "foo")

