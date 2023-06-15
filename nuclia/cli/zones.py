from nuclia.cli.auth import NucliaAuth
from nuclia.data import get_auth


class NucliaZones:
    @property
    def _auth(self) -> NucliaAuth:
        return get_auth()

    def list(self):
        return self._auth.zones()
