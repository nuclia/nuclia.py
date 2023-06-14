from nuclia import BASE
from nuclia.cli.auth import NucliaAuth
from nuclia.data import get_auth

LIST_KBS = BASE + "/api/v1/account/{account}/kbs"
ADD_KB = BASE + "/api/v1/account/{account}/kbs"


class NucliaNUA:
    @property
    def _auth(self) -> NucliaAuth:
        auth = get_auth()
        return auth

    def usage(self, id: str):
        pass
