from nuclia.config import retrieve_nua
from nuclia.data import get_auth
from nuclia.sdk.auth import NucliaAuth

ADD_NUA = "/api/v1/account/{account}/nua_clients"


class NucliaNUAS:
    @property
    def _auth(self) -> NucliaAuth:
        auth = get_auth()
        return auth

    def list(self):
        result = []
        result.extend(
            self._auth._config.nuas_token
            if self._auth._config.nuas_token is not None
            else []
        )
        return result

    def default(self, nua: str):
        nuas = (
            self._auth._config.nuas_token
            if self._auth._config.nuas_token is not None
            else []
        )
        nua_obj = retrieve_nua(nuas, nua)

        if nua_obj is None:
            raise KeyError("NUA KEY not found")
        self._auth._config.set_default_nua(nua_obj.client_id)
        self._auth._config.save()

    def add(self, account: str, slug: str):
        raise NotImplementedError()
        # path = ADD_NUA.format(account=account)
        # return self._auth.post_user(path)
