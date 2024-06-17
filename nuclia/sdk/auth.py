import base64
import json
import webbrowser
from typing import Any, Dict, List, Optional, Tuple

from httpx import AsyncClient, Client, ConnectError
from prompt_toolkit import prompt

from nuclia import get_global_url, get_regional_url
from nuclia.config import (
    Account,
    Config,
    KnowledgeBox,
    Zone,
    retrieve_account,
    retrieve_nua,
)
from nuclia.exceptions import NeedUserToken, UserTokenExpired

USER = "/api/v1/user/welcome"
MEMBER = "/api/v1/user"
ACCOUNTS = "/api/v1/accounts"
ZONES = "/api/v1/zones"
LIST_KBS = "/api/v1/account/{account}/kbs"
VERIFY_NUA = "/api/authorizer/info"


class BaseNucliaAuth:
    _inner_config: Optional[Config] = None

    @property
    def _config(self) -> Config:
        if self._inner_config is None:
            from nuclia.data import get_config

            self._inner_config = get_config()
        return self._inner_config

    def get_account_id(self, account_slug: str) -> str:
        account_obj = retrieve_account(self._config.accounts or [], account_slug)
        if not account_obj:
            raise ValueError(f"Account {account_slug} not found")
        return account_obj.id

    def list_nuas(self):
        result = []
        result.extend(
            self._config.nuas_token if self._config.nuas_token is not None else []
        )
        return result

    def default_nua(self, nua: str):
        nuas = self._config.nuas_token if self._config.nuas_token is not None else []
        nua_obj = retrieve_nua(nuas, nua)

        if nua_obj is None:
            raise KeyError("NUA KEY not found")
        self._config.set_default_nua(nua_obj.client_id)
        self._config.save()

    def default_kb(self, kbid: str):
        self._config.set_default_kb(kbid=kbid)

    def unset_kb(self, kbid: str):
        self._config.unset_default_kb(kbid=kbid)


class NucliaAuth(BaseNucliaAuth):
    client = Client()

    def show(self):
        if self._config.default:
            if self._config.default.account:
                print("Default Account")
                print("===============")
                print()
                print(self._config.default.account)
                print()
            if self._config.default.kbid:
                print("Default Knowledge Box")
                print("=====================")
                print()
                print(self._config.get_kb(self._config.default.kbid))
                print()
            if self._config.default.nua:
                print("Default NUA")
                print("===========")
                print()
                print(self._config.get_nua(self._config.default.nua))
                print()
            if self._config.default.nucliadb:
                print("Default NUCLIADB")
                print("================")
                print()
                print(self._config.default.nucliadb)
                print()

        if self._config.token:
            print("User Auth")
            print("=========")
            print()
            try:
                self._show_user()
            except Exception:
                print("Not Authenticated")
            print()

        if len(self._config.kbs_token):
            print("Knowledgebox Auth")
            print("=================")
            print()
            for kb in self._config.kbs_token:
                print(kb)
            print()

        if len(self._config.nuas_token):
            print("NUA Key")
            print("=======")
            print()
            for nua in self._config.nuas_token:
                print(nua)

    def nucliadb(self, url: str = "http://localhost:8080"):
        """
        Setup a local NucliaDB. Needs to be the base url of the NucliaDB server
        """
        resp = self.client.get(url)
        if resp.status_code != 200 or b"Nuclia" not in resp.content:
            raise Exception("Not a valid URL")
        self._config.set_default_nucliadb(nucliadb=url)

    def kb(self, url: str, token: Optional[str] = None) -> Optional[str]:
        url = url.strip("/")
        kbid, title = self.validate_kb(url, token)
        if kbid:
            print("Validated")
            self._config.set_kb_token(url=url, token=token, title=title, kbid=kbid)
            self._config.set_default_kb(kbid=kbid)
        else:
            print("Invalid service token")
        return kbid

    def nua(self, token: str) -> Optional[str]:
        client_id, account_type, account, base_region = self.validate_nua(token)
        if account is not None and client_id is not None and base_region is not None:
            print("Validated")
            self._config.set_nua_token(
                client_id=client_id,
                account_type=account_type,
                account=account,
                base_region=base_region,
                token=token,
            )
            return client_id
        else:
            print("Invalid NUA token")
            return None

    def validate_nua(
        self, token: str
    ) -> Tuple[Optional[str], Optional[str], Optional[str], Optional[str]]:
        # Validate the code is ok
        token_payload = token.split(".")[1]
        token_payload_decoded = str(base64.b64decode(token_payload + "=="), "utf-8")
        payload = json.loads(token_payload_decoded)
        base_path = payload["iss"]
        url = base_path.strip("/") + VERIFY_NUA
        resp = self.client.get(
            url,
            headers={"x-nuclia-nuakey": f"Bearer {token}"},
        )
        if resp.status_code == 200:
            data = resp.json().get("user")
            return (
                data.get("user_id"),
                data.get("account_type"),
                data.get("account_id"),
                payload.get("iss"),
            )
        else:
            return None, None, None, None

    def validate_kb(
        self, url: str, token: Optional[str] = None
    ) -> Tuple[Optional[str], Optional[str]]:
        # Validate the code is ok
        if token is None:
            # Validate OSS version
            resp = self.client.get(
                url,
                headers={"X-NucliaDB-ROLES": "READER"},
            )
        else:
            # Validate Cloud version
            resp = self.client.get(
                url,
                headers={"X-Nuclia-Serviceaccount": f"Bearer {token}"},
            )
        if resp.status_code == 200:
            data = resp.json()
            return data.get("uuid"), data.get("config", {}).get("title")
        else:
            return None, None

    def _show_user(self):
        resp = self._request("GET", get_global_url(MEMBER))
        assert resp
        print(f"User: {resp.get('name')} <{resp.get('email')}>")
        print(f"Type: {resp.get('type')}")

    def login(self):
        """
        Lets redirect the user to the UI to capture a token
        """
        if self._validate_user_token():
            print("Logged in!")
            self._show_user()
            return

        webbrowser.open(get_global_url("/redirect?display=token"))
        # we cannot use Python's `input` here because the copy/pasted token is too long
        code = prompt("Follow the browser flow and copy the token and paste it here:")
        print("Checking...")
        self.set_user_token(code)

    def logout(self):
        """
        Remove the current user token.
        """
        self._config.remove_user_token()

    def set_user_token(self, code: str):
        if self._validate_user_token(code):
            self._config.set_user_token(code)
            print("Auth completed!")
            self.post_login()
        else:
            print("Invalid token auth not completed")

    def _extract_account(self, token: str) -> str:
        base64url = token.split(".")[1]
        data = json.loads(
            base64.urlsafe_b64decode(base64url + "=" * (4 - len(base64url) % 4))
        )
        return data.get("jti")

    def _validate_user_token(self, code: Optional[str] = None) -> bool:
        # Validate the code is ok
        if code is None:
            code = self._config.token
        resp = self.client.get(
            get_global_url(USER),
            headers={"Authorization": f"Bearer {code}"},
        )
        if resp.status_code == 200:
            return True
        else:
            return False

    def post_login(self):
        self.accounts()
        self.zones()

    def _request(
        self, method: str, path: str, data: Optional[Any] = None, remove_null=True
    ):
        if not self._config.token:
            raise NeedUserToken()
        kwargs: Dict[str, Any] = {
            "headers": {"Authorization": f"Bearer {self._config.token}"}
        }
        if data is not None:
            if remove_null:
                data = {k: v for k, v in data.items() if v is not None}
            kwargs["data"] = json.dumps(data)
        resp = self.client.request(
            method,
            path,
            **kwargs,
        )
        if resp.status_code == 204:
            return None
        elif resp.status_code >= 200 and resp.status_code < 300:
            return resp.json()
        elif resp.status_code >= 300 and resp.status_code < 400:
            return None
        elif resp.status_code == 403:
            raise UserTokenExpired()
        else:
            raise Exception({"status": resp.status_code, "message": resp.text})

    def accounts(self) -> List[Account]:
        accounts = self._request("GET", get_global_url(ACCOUNTS))
        result: List[Account] = []
        self._config.accounts = []
        if accounts is None:
            return result
        for account in accounts:
            account_obj = Account.parse_obj(account)
            result.append(account_obj)
            self._config.accounts.append(account_obj)
        self._config.save()
        return result

    def zones(self) -> List[Zone]:
        zones = self._request("GET", get_global_url(ZONES))
        if self._config.accounts is None:
            self._config.accounts = []
        self._config.zones = []
        result: List[Zone] = []
        if zones is None:
            return result
        for zone in zones:
            zone_obj = Zone.parse_obj(zone)
            result.append(zone_obj)
            self._config.zones.append(zone_obj)
        self._config.save()
        return result

    def kbs(self, account: str) -> List[KnowledgeBox]:
        result: List[KnowledgeBox] = []
        zones = self.zones()
        for zoneObj in zones:
            zoneSlug = zoneObj.slug
            if not zoneSlug:
                continue
            path = get_regional_url(zoneSlug, LIST_KBS.format(account=account))
            try:
                kbs = self._request("GET", path)
            except UserTokenExpired:
                return []
            except ConnectError:
                print(
                    f"Connection error to {get_regional_url(zoneSlug, '')}, skipping zone"
                )
                continue
            if kbs is not None:
                for kb in kbs:
                    url = get_regional_url(zoneSlug, f"/api/v1/kb/{kb['id']}")
                    kb_obj = KnowledgeBox(
                        url=url,
                        id=kb["id"],
                        slug=kb["slug"],
                        title=kb["title"],
                        account=account,
                        region=zoneSlug,
                    )
                    result.append(kb_obj)
        return result


class AsyncNucliaAuth(BaseNucliaAuth):
    client = AsyncClient()

    async def show(self):
        if self._config.default:
            if self._config.default.account:
                print("Default Account")
                print("===============")
                print()
                print(self._config.default.account)
                print()
            if self._config.default.kbid:
                print("Default Knowledge Box")
                print("=====================")
                print()
                print(self._config.get_kb(self._config.default.kbid))
                print()

        if self._config.token:
            print("User Auth")
            print("=========")
            print()
            try:
                await self._show_user()
            except Exception:
                print("Not Authenticated")
            print()

        if len(self._config.kbs_token):
            print("Knowledgebox Auth")
            print("=================")
            print()
            for kb in self._config.kbs_token:
                print(kb)
            print()

        if len(self._config.nuas_token):
            print("NUA Key")
            print("=======")
            print()
            for nua in self._config.nuas_token:
                print(nua)

    async def nucliadb(self, url: str = "http://localhost:8080"):
        """
        Setup a local NucliaDB. Needs to be the base url of the NucliaDB server
        """
        resp = await self.client.get(url)
        if resp.status_code != 200 or b"Nuclia" not in resp.content:
            raise Exception("Not a valid URL")
        self._config.set_default_nucliadb(nucliadb=url)

    async def kb(self, url: str, token: Optional[str] = None) -> bool:
        url = url.strip("/")
        kbid, title = await self.validate_kb(url, token)
        if kbid:
            print("Validated")
            self._config.set_kb_token(url=url, token=token, title=title, kbid=kbid)
            self._config.set_default_kb(kbid=kbid)
            return True
        else:
            print("Invalid service token")
            return False

    async def nua(self, token: str) -> Optional[str]:
        client_id, account_type, account, base_region = await self.validate_nua(token)
        if account is not None and client_id is not None and base_region is not None:
            print("Validated")
            self._config.set_nua_token(
                client_id=client_id,
                account_type=account_type,
                account=account,
                base_region=base_region,
                token=token,
            )
            return client_id
        else:
            print("Invalid NUA token")
            return None

    async def validate_nua(
        self, token: str
    ) -> Tuple[Optional[str], Optional[str], Optional[str], Optional[str]]:
        # Validate the code is ok
        token_payload = token.split(".")[1]
        token_payload_decoded = str(base64.b64decode(token_payload + "=="), "utf-8")
        payload = json.loads(token_payload_decoded)
        base_path = payload["iss"]
        url = base_path.strip("/") + VERIFY_NUA
        resp = await self.client.get(
            url,
            headers={"x-nuclia-nuakey": f"Bearer {token}"},
        )
        if resp.status_code == 200:
            data = resp.json().get("user")
            return (
                data.get("user_id"),
                data.get("account_type"),
                data.get("account_id"),
                payload.get("iss"),
            )
        else:
            return None, None, None, None

    async def validate_kb(
        self, url: str, token: Optional[str] = None
    ) -> Tuple[Optional[str], Optional[str]]:
        # Validate the code is ok
        if token is None:
            # Validate OSS version
            resp = await self.client.get(
                url,
                headers={"X-NucliaDB-ROLES": "READER"},
            )
        else:
            # Validate Cloud version
            resp = await self.client.get(
                url,
                headers={"X-Nuclia-Serviceaccount": f"Bearer {token}"},
            )
        if resp.status_code == 200:
            data = resp.json()
            return data.get("uuid"), data.get("config", {}).get("title")
        else:
            return None, None

    async def _show_user(self):
        resp = await self._request("GET", get_global_url(MEMBER))
        assert resp
        print(f"User: {resp.get('name')} <{resp.get('email')}>")
        print(f"Type: {resp.get('type')}")

    async def login(self):
        """
        Lets redirect the user to the UI to capture a token
        """
        if await self._validate_user_token():
            print("Logged in!")
            await self._show_user()
            return

        webbrowser.open(get_global_url("/redirect?display=token"))
        # we cannot use Python's `input` here because the copy/pasted token is too long
        code = prompt("Follow the browser flow and copy the token and paste it here:")
        print("Checking...")
        await self.set_user_token(code)

    def logout(self):
        """
        Remove the current user token.
        """
        self._config.remove_user_token()

    async def set_user_token(self, code: str):
        if await self._validate_user_token(code):
            self._config.set_user_token(code)
            print("Auth completed!")
            await self.post_login()
        else:
            print("Invalid token auth not completed")

    def _extract_account(self, token: str) -> str:
        base64url = token.split(".")[1]
        data = json.loads(
            base64.urlsafe_b64decode(base64url + "=" * (4 - len(base64url) % 4))
        )
        return data.get("jti")

    async def _validate_user_token(self, code: Optional[str] = None) -> bool:
        # Validate the code is ok
        if code is None:
            code = self._config.token
        resp = await self.client.get(
            get_global_url(USER),
            headers={"Authorization": f"Bearer {code}"},
        )
        if resp.status_code == 200:
            return True
        else:
            return False

    async def post_login(self):
        await self.accounts()
        await self.zones()

    async def _request(
        self, method: str, path: str, data: Optional[Any] = None, remove_null=True
    ):
        if not self._config.token:
            raise NeedUserToken()
        kwargs: Dict[str, Any] = {
            "headers": {"Authorization": f"Bearer {self._config.token}"}
        }
        if data is not None:
            if remove_null:
                data = {k: v for k, v in data.items() if v is not None}
            kwargs["data"] = json.dumps(data)
        resp = await self.client.request(
            method,
            path,
            **kwargs,
        )
        if resp.status_code == 204:
            return None
        elif resp.status_code >= 200 and resp.status_code < 300:
            return resp.json()
        elif resp.status_code >= 300 and resp.status_code < 400:
            return None
        elif resp.status_code == 403:
            raise UserTokenExpired()
        else:
            raise Exception({"status": resp.status_code, "message": resp.text})

    async def accounts(self) -> List[Account]:
        accounts = await self._request("GET", get_global_url(ACCOUNTS))
        result: List[Account] = []
        self._config.accounts = []
        if accounts is None:
            return result
        for account in accounts:
            account_obj = Account.parse_obj(account)
            result.append(account_obj)
            self._config.accounts.append(account_obj)
        self._config.save()
        return result

    async def zones(self) -> List[Zone]:
        zones = await self._request("GET", get_global_url(ZONES))
        if self._config.accounts is None:
            self._config.accounts = []
        self._config.zones = []
        result: List[Zone] = []
        if zones is None:
            return result
        for zone in zones:
            zone_obj = Zone.parse_obj(zone)
            result.append(zone_obj)
            self._config.zones.append(zone_obj)
        self._config.save()
        return result

    async def kbs(self, account: str) -> List[KnowledgeBox]:
        result: List[KnowledgeBox] = []
        zones = await self.zones()
        for zoneObj in zones:
            zoneSlug = zoneObj.slug
            if not zoneSlug:
                continue
            path = get_regional_url(zoneSlug, LIST_KBS.format(account=account))
            try:
                kbs = await self._request("GET", path)
            except UserTokenExpired:
                return result
            except ConnectionError:
                print(
                    f"Connection error to {get_regional_url(zoneSlug, '')}, skipping zone"
                )
                continue
            if kbs is not None:
                for kb in kbs:
                    url = get_regional_url(zoneSlug, f"/api/v1/kb/{kb['id']}")
                    kb_obj = KnowledgeBox(
                        url=url,
                        id=kb["id"],
                        slug=kb["slug"],
                        title=kb["title"],
                        account=account,
                        region=zoneSlug,
                    )
                    result.append(kb_obj)
        return result
