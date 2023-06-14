from nuclia.cli.auth import NucliaAuth
from nuclia.data import get_auth


class NucliaSearch:
    @property
    def _auth(self) -> NucliaAuth:
        auth = get_auth()
        return auth
