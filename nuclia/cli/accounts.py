from nuclia.cli.auth import NucliaAuth
from nuclia.data import get_auth


class NucliaAccounts:
    @property
    def _auth(self) -> NucliaAuth:
        return get_auth()

    def list(self):
        return self._auth.accounts()
