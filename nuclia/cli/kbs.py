from typing import Dict, Optional

from nuclia import BASE
from nuclia.cli.auth import NucliaAuth
from nuclia.config import Account, KnowledgeBox
from nuclia.data import get_auth
from nuclia.decorators import accounts

ADD_KB = BASE + "/api/v1/account/{account}/kbs"


class NucliaKBS:
    @property
    def _auth(self) -> NucliaAuth:
        auth = get_auth()
        return auth

    @accounts
    def list(self, account: Optional[str] = None):
        if account is None:
            result = []
            for account_obj in self._auth._config.accounts:
                result.extend(self._auth.kbs(account_obj.slug))
            self._auth._config.kbs = result
            self._auth._config.save()
            return result
        else:
            return self._auth.kbs(account)

    def add(
        self,
        account: str,
        slug: str,
        anonymization: Optional[str] = None,
        description: Optional[str] = None,
        learning_configuration: Optional[Dict[str, str]] = None,
        sentence_embedder: Optional[str] = None,
        title: Optional[str] = None,
        zone: Optional[str] = None,
    ):
        path = ADD_KB.format(account=account)

        return self._auth.post_user(path)

    def default(self, *, account: str, kb: str):
        try:
            account_obj: Account = next(
                filter(lambda x: x.slug == account, self._auth._config.accounts)
            )
        except StopIteration:
            try:
                account_obj: Account = next(
                    filter(lambda x: x.id == account, self._auth._config.accounts)
                )
            except StopIteration:
                print(f"Account not found {account}")
                return

        self._auth._config.default.account = account_obj.id

        try:
            kb_obj: KnowledgeBox = next(
                filter(lambda x: x.slug == kb, self._auth._config.kbs)
            )
        except StopIteration:
            try:
                kb_obj: KnowledgeBox = next(
                    filter(lambda x: x.id == kb, self._auth._config.kbs)
                )
            except StopIteration:
                print(f"KB not found {kb}")
                return

        self._auth._config.default.kbid = kb_obj.id
        self._auth._config.save()

    def delete(self, account: str, slug: str):
        path = ADD_KB.format(account=account)
        return self._auth.post_user(path)
