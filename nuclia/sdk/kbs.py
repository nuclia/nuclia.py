from typing import Dict, Optional

from nuclia import USE_NEW_REGIONAL_ENDPOINTS, get_global_url, get_regional_url
from nuclia.config import retrieve, retrieve_account
from nuclia.data import get_auth
from nuclia.decorators import account, accounts, zone
from nuclia.sdk.auth import NucliaAuth

KBS_ENDPOINT = "/api/v1/account/{account}/kbs"
KB_ENDPOINT = "/api/v1/account/{account}/kb/{kb}"


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
                    account_id = (
                        USE_NEW_REGIONAL_ENDPOINTS and account_obj.id
                    ) or account_obj.slug
                    result.extend(self._auth.kbs(account_id))
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
            if not USE_NEW_REGIONAL_ENDPOINTS:
                return self._auth.kbs(account)
            else:
                matching_account = retrieve_account(self._auth._config.accounts or [], account)
                if not matching_account:
                    raise ValueError("Account not found")
                return self._auth.kbs(matching_account.id)

    @accounts
    @account
    @zone
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
        if not slug:
            raise ValueError("slug is required.")
        if USE_NEW_REGIONAL_ENDPOINTS:
            if not zone:
                raise ValueError("zone is required")
            path = get_regional_url(
                zone, KBS_ENDPOINT.format(account=kwargs["account_id"])
            )
        else:
            path = get_global_url(KBS_ENDPOINT.format(account=kwargs["account"]))
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
        return self.get(slug, account_id=kwargs["account_id"], zone=zone)

    @accounts
    @account
    @zone
    def get(
        self,
        slug: Optional[str]=None,
        id: Optional[str]=None,
        **kwargs,
    ):
        if USE_NEW_REGIONAL_ENDPOINTS:
            zone = kwargs.get("zone")
            if not zone:
                raise ValueError("zone is required")
            if not id and not slug:
                raise ValueError("id or slug is required")
            if slug and not id:
                kbs = self._auth.kbs(kwargs["account_id"])
                kb_obj = retrieve(kbs, slug)
                if not kb_obj:
                    raise ValueError("Knowledge Box not found")
                id = kb_obj.id
            path = get_regional_url(
                zone, KB_ENDPOINT.format(account=kwargs["account_id"], kb=id)
            )
        else:
            path = get_global_url(
                KB_ENDPOINT.format(account=kwargs["account"], kb=slug)
            )
        return self._auth._request("GET", path)

    @accounts
    @account
    @zone
    def delete(
        self,
        slug: Optional[str]=None,
        id: Optional[str]=None,
        **kwargs,
    ):
        if USE_NEW_REGIONAL_ENDPOINTS:
            zone = kwargs.get("zone")
            if not zone:
                raise ValueError("zone is required")
            if not id and not slug:
                raise ValueError("id or slug is required")
            if slug and not id:
                kbs = self._auth.kbs(kwargs["account_id"])
                kb_obj = retrieve(kbs, slug)
                if not kb_obj:
                    raise ValueError("Knowledge Box not found")
                id = kb_obj.id
            path = get_regional_url(
                zone, KB_ENDPOINT.format(account=kwargs["account_id"], kb=id)
            )
        else:
            path = get_global_url(
                KB_ENDPOINT.format(account=kwargs["account"], kb=slug)
            )
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
