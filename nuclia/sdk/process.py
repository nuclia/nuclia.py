from nuclia.data import get_auth
from nuclia.sdk.auth import NucliaAuth


class NucliaProcess:
    @property
    def _auth(self) -> NucliaAuth:
        auth = get_auth()
        return auth
