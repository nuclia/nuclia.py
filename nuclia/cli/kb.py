from nuclia.cli.auth import NucliaAuth
from nuclia.cli.search import NucliaSearch
from nuclia.cli.upload import NucliaUpload
from nuclia.data import get_auth
from nuclia.decorators import kb
from nuclia.lib.kb import NucliaDBClient


class NucliaKB:
    @property
    def _auth(self) -> NucliaAuth:
        auth = get_auth()
        return auth

    def __init__(self):
        self.upload = NucliaUpload()
        self.search = NucliaSearch()

    @kb
    def list(self, ndb: NucliaDBClient):
        return ndb.ndb.list_resources(kbid=ndb.kbid)
