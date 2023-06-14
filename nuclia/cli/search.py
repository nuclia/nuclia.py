from nuclia.cli.auth import NucliaAuth
from nuclia.data import get_auth
from nuclia.decorators import kb
from nuclia.lib.kb import NucliaDBClient
from nucliadb_models.search import ChatRequest, FindRequest


class NucliaSearch:
    @property
    def _auth(self) -> NucliaAuth:
        auth = get_auth()
        return auth

    @kb
    def find(self, *, ndb: NucliaDBClient, query: str):
        return ndb.ndb.find(FindRequest(query=query), kbid=ndb.kbid)

    @kb
    def ask(self, *, ndb: NucliaDBClient, query: str):
        return ndb.chat(ChatRequest(query=query))
