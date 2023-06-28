from nucliadb_models.resource import Resource, ResourceList

from nuclia.data import get_auth
from nuclia.decorators import kb, pretty
from nuclia.lib.kb import NucliaDBClient
from nuclia.sdk.auth import NucliaAuth
from nuclia.sdk.search import NucliaSearch
from nuclia.sdk.upload import NucliaUpload


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
    @pretty
    def get_resource_by_id(self, *, ndb: NucliaDBClient, rid: str, **kwargs) -> Resource:
        return ndb.ndb.get_resource_by_id(
            kbid=ndb.kbid, rid=rid, query_params={"show": "values"}
        )

    @kb
    @pretty
    def get_resource_by_slug(self, *, ndb: NucliaDBClient, slug: str, **kwargs) -> Resource:
        return ndb.ndb.get_resource_by_slug(
            kbid=ndb.kbid, slug=slug, query_params={"show": "values"}
        )

    @kb
    def delete(self, *, ndb: NucliaDBClient, rid: str):
        ndb.ndb.delete_resource(kbid=ndb.kbid, rid=rid)
