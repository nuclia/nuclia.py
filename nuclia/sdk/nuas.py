from nuclia import BASE
from nuclia.config import NuaKey
from nuclia.data import get_auth
from nuclia.sdk.auth import NucliaAuth

LIST_NUAS = BASE + "/api/v1/account/{account}/nua_clients"
ADD_NUA = BASE + "/api/v1/account/{account}/nua_clients"


class NucliaNUAS:
    @property
    def _auth(self) -> NucliaAuth:
        auth = get_auth()
        return auth

    def list(self, account: str):
        path = LIST_NUAS.format(account=account)
        nuas = self._auth.get_user(path)
        result = []
        for nua in nuas.get("clients", []):
            result.append(NuaKey.parse_obj(nua))
        return result

    def add(self, account: str, slug: str):
        raise NotImplementedError()
        # path = ADD_NUA.format(account=account)
        # return self._auth.post_user(path)

    def delete(self, account: str, slug: str):
        raise NotImplementedError()
        # path = ADD_NUA.format(account=account)
        # return self._auth.post_user(path)
