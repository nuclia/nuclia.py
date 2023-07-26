from nuclia.data import get_auth
from nuclia.sdk.auth import NucliaAuth


class NucliaAccounts:
    @property
    def _auth(self) -> NucliaAuth:
        return get_auth()

    def list(self):
        return self._auth.accounts()

    def default(self, account: str):
        accounts = (
            self._auth._config.accounts
            if self._auth._config.accounts is not None
            else []
        )
        slugs = [account_obj.slug for account_obj in accounts]
        if account not in slugs:
            raise KeyError("Account not found")
        self._auth._config.set_default_account(account)
        self._auth._config.save()
