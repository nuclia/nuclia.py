from typing import Dict, Optional

from nuclia import BASE
from nuclia.config import retrieve
from nuclia.data import get_auth
from nuclia.decorators import account, accounts
from nuclia.sdk.auth import NucliaAuth

KBS_ENDPOINT = BASE + "/api/v1/account/{account}/kbs"
KB_ENDPOINT = BASE + "/api/v1/account/{account}/kb/{slug}"


class NucliaKBS:
    @property
    def _auth(self) -> NucliaAuth:
        auth = get_auth()
        return auth

    @accounts
    def list(self, account: Optional[str] = None):
        if account is None:
            result = []
            accounts = (
                self._auth._config.accounts
                if self._auth._config.accounts is not None
                else []
            )
            for account_obj in accounts:
                if account_obj.slug is not None:
                    result.extend(self._auth.kbs(account_obj.slug))
            self._auth._config.kbs = result
            self._auth._config.save()

            # List the Knowledge Boxes configured as Service Token
            result.extend(
                self._auth._config.kbs_token
                if self._auth._config.kbs_token is not None
                else []
            )

            return result
        else:
            return self._auth.kbs(account)

    @accounts
    @account
    def add(
        self,
        slug: str,
        anonymization: Optional[str] = None,
        description: Optional[str] = None,
        learning_configuration: Optional[Dict[str, str]] = None,
        sentence_embedder: Optional[str] = None,
        title: Optional[str] = None,
        zone: Optional[str] = "europe-1",
        **kwargs,
    ):
        account = kwargs["account"]
        path = KBS_ENDPOINT.format(account=account)
        data = {
            "slug": slug,
            "anonymization": anonymization,
            "description": description,
            "learning_configuration": learning_configuration,
            "sentence_embedder": sentence_embedder,
            "title": title or slug,
            "zone": zone,
        }
        self._auth._request("POST", path, data)
        return self.get(slug, account=account)

    @accounts
    @account
    def get(
        self,
        slug: str,
        **kwargs,
    ):
        account = kwargs["account"]
        path = KB_ENDPOINT.format(account=account, slug=slug)
        return self._auth._request("GET", path)

    @accounts
    @account
    def delete(
        self,
        slug: str,
        **kwargs,
    ):
        account = kwargs["account"]
        path = KB_ENDPOINT.format(account=account, slug=slug)
        return self._auth._request("DELETE", path)

    def default(self, kb: str):
        kbs = self._auth._config.kbs if self._auth._config.kbs is not None else []
        kb_obj = retrieve(kbs, kb)
        if kb_obj is None:
            kbs = (
                self._auth._config.kbs_token
                if self._auth._config.kbs_token is not None
                else []
            )
            kb_obj = retrieve(kbs, kb)

        if kb_obj is None:
            raise KeyError("Knowledge Box not found")
        self._auth._config.set_default_kb(kb_obj.id)
        self._auth._config.save()
