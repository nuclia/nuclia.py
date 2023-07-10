from nuclia.sdk.logger import logger
from nuclia.sdk.resource import NucliaResource
from nucliadb_models.resource import Resource, ResourceList

from nuclia.data import get_auth
from nuclia.decorators import kb, pretty
from nuclia.sdk.auth import NucliaAuth
from nuclia.sdk.search import NucliaSearch
from nuclia.sdk.upload import NucliaUpload
from warnings import warn

class NucliaKB:
    @property
    def _auth(self) -> NucliaAuth:
        auth = get_auth()
        return auth

    def __init__(self):
        self.upload = NucliaUpload()
        self.search = NucliaSearch()
        self.resource = NucliaResource()

    @kb
    def list(self, **kwargs):
        ndb = kwargs["ndb"]
        data: ResourceList = ndb.ndb.list_resources(kbid=ndb.kbid)
        for resource in data.resources:
            print(f"{resource.id} {resource.icon:30} {resource.title}")

    @kb
    @pretty
    def get_resource_by_id(self, *, rid: str, **kwargs) -> Resource:
        warn('get_resource_by_slug is deprecated, use resource.get instead', DeprecationWarning)
        logger.warning('get_resource_by_slug is deprecated, use resource.get instead')
        ndb = kwargs["ndb"]
        return ndb.ndb.get_resource_by_id(
            kbid=ndb.kbid, rid=rid, query_params={"show": "values"}
        )

    @kb
    @pretty
    def get_resource_by_slug(self, *, slug: str, **kwargs) -> Resource:
        warn('get_resource_by_slug is deprecated, use resource.get instead', DeprecationWarning)
        logger.warning('get_resource_by_slug is deprecated, use resource.get instead')
        ndb = kwargs["ndb"]
        return ndb.ndb.get_resource_by_slug(
            kbid=ndb.kbid, slug=slug, query_params={"show": "values"}
        )

    @kb
    def delete(self, *, rid: str, **kwargs):
        warn('delete is deprecated, use resource.delete instead', DeprecationWarning)
        logger.warning('delete is deprecated, use resource.delete instead')
        ndb = kwargs["ndb"]
        ndb.ndb.delete_resource(kbid=ndb.kbid, rid=rid)
