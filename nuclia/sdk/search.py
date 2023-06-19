from typing import Union

from nucliadb_models.search import ChatRequest, FindRequest

from nuclia.data import get_auth
from nuclia.decorators import kb
from nuclia.lib.kb import NucliaDBClient
from nuclia.sdk.auth import NucliaAuth


class NucliaSearch:
    @property
    def _auth(self) -> NucliaAuth:
        auth = get_auth()
        return auth

    @kb
    def find(self, *, ndb: NucliaDBClient, query: Union[str, FindRequest]):
        if isinstance(query, str):
            req = FindRequest(query=query)
        else:
            req = query

        return ndb.ndb.find(req, kbid=ndb.kbid)

    @kb
    def ask(self, *, ndb: NucliaDBClient, query: Union[str, ChatRequest]):
        if isinstance(query, str):
            req = ChatRequest(query=query)
        else:
            req = query
        return ndb.chat(req)
