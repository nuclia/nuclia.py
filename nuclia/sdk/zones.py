from nuclia.data import get_auth
from nuclia.sdk.auth import NucliaAuth


class NucliaZones:
    @property
    def _auth(self) -> NucliaAuth:
        return get_auth()

    def list(self):
        return self._auth.zones()
