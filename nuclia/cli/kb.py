from nucliadb_models.resource import ResourceList

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
    def list(self, *, ndb: NucliaDBClient):
        data: ResourceList = ndb.ndb.list_resources(kbid=ndb.kbid)
        for resource in data.resources:
            print(f"{resource.id} {resource.icon:30} {resource.title}")

    @kb
    def delete(self, *, ndb: NucliaDBClient, rid: str):
        ndb.ndb.delete_resource(kbid=ndb.kbid, rid=rid)