from typing import Optional

from nucliadb_models.resource import KnowledgeBoxList, KnowledgeBoxObj

from nuclia.data import get_auth
from nuclia.decorators import nucliadb
from nuclia.lib.kb import NucliaDBClient
from nuclia.sdk.auth import NucliaAuth


class NucliaDB:
    @property
    def _auth(self) -> NucliaAuth:
        auth = get_auth()
        return auth

    @nucliadb
    def list(self, **kwargs) -> KnowledgeBoxList:
        ndb: NucliaDBClient = kwargs["ndb"]
        return ndb.ndb.list_knowledge_boxes()

    @nucliadb
    def create(
        self,
        *,
        slug: str,
        title: str,
        learning_configuration: Optional[dict] = None,
        default: bool = False,
        **kwargs,
    ) -> KnowledgeBoxObj:
        ndb: NucliaDBClient = kwargs["ndb"]
        kb: KnowledgeBoxObj = ndb.ndb.create_knowledge_box(
            slug=slug, title=title, learning_configuration=learning_configuration
        )
        if default:
            self._auth.kb(url=f"{ndb.ndb.base_url}/v1/kb/{kb.uuid}")
        return kb

    @nucliadb
    def delete(
        self,
        *,
        kbid: str,
        **kwargs,
    ) -> None:
        ndb: NucliaDBClient = kwargs["ndb"]
        ndb.ndb.delete_knowledge_box(kbid=kbid)
        self._auth.unset_kb(kbid=kbid)
