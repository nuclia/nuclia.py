import base64
import json
import webbrowser
from typing import Any, Dict, List, Optional, Tuple

import requests
from prompt_toolkit import prompt

from nuclia import BASE, BASE_DOMAIN, get_global_url
from nuclia.cli.utils import yes_no
from nuclia.config import Account, Config, KnowledgeBox, Zone
from nuclia.exceptions import NeedUserToken, UserTokenExpired

USER = f"{BASE}/api/v1/user/welcome"
MEMBER = f"{BASE}/api/v1/user"
ACCOUNTS = f"{BASE}/api/v1/accounts"
ZONES = f"{BASE}/api/v1/zones"
LIST_KBS = BASE + "/api/v1/account/{account}/kbs"
VERIFY_NUA = "/api/authorizer/info"


class NucliaAuth:
    _inner_config: Optional[Config] = None

    @property
    def _config(self) -> Config:
        if self._inner_config is None:
            from nuclia.data import get_config

            self._inner_config = get_config()
        return self._inner_config

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
        resp = requests.get(url)
        if resp.status_code != 200 or b"Nuclia" not in resp.content:
            raise Exception("Not a valid URL")
        self._config.set_default_nucliadb(nucliadb=url)

    def unset_kb(self, kbid: str):
        self._config.unset_default_kb(kbid=kbid)

    def kb(self, url: str, token: Optional[str] = None, interactive: bool = True):
        url = url.strip("/")
        kbid, title = self.validate_kb(url, token)
        if kbid:
            print("Validated")
            try:
                next(
                    filter(
                        lambda x: x.id == kbid,
                        self._config.kbs if self._config.kbs is not None else [],
                    )
                )
                if (
                    interactive
                    and yes_no(f"Want to replace actual KB {kbid} configuration")
                    is False
                ):
                    print("Cancelling operation")
                    return

            except StopIteration:
                # Not found
                pass

            self._config.set_kb_token(
                url=url, token=token, title=title, kbid=kbid, interactive=interactive
            )
        else:
            print("Invalid service token")

    def nua(self, region: str, token: str) -> Optional[str]:
        client_id, account_type, account = self.validate_nua(token, region)
        if account is not None and client_id is not None:
            print("Validated")
            self._config.set_nua_token(
                client_id=client_id,
                account_type=account_type,
                account=account,
                region=region,
                token=token,
            )
            return client_id
        else:
            print("Invalid service token")
            return None

    def validate_nua(
        self, token: str, region: Optional[str] = None
    ) -> Tuple[Optional[str], Optional[str], Optional[str]]:
        # Validate the code is ok
        url = get_global_url(VERIFY_NUA)
        resp = requests.get(
            url,
            headers={"x-nuclia-nuakey": f"Bearer {token}"},
        )
        if resp.status_code == 200:
            data = resp.json().get("user")
            return data.get("user_id"), data.get("account_type"), data.get("account_id")
        else:
            return None, None, None

    def validate_kb(
        self, url: str, token: Optional[str] = None
    ) -> Tuple[Optional[str], Optional[str]]:
        # Validate the code is ok
        if token is None:
            # Validate OSS version
            resp = requests.get(
                url,
                headers={"X-NucliaDB-ROLES": f"READER"},
            )
        else:
            # Validate Cloud version
            resp = requests.get(
                url,
                headers={"X-Nuclia-Serviceaccount": f"Bearer {token}"},
            )
        if resp.status_code == 200:
            data = resp.json()
            return data.get("uuid"), data.get("config", {}).get("title")
        else:
            return None, None

    def _show_user(self):
        resp = self._request("GET", MEMBER)
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
        resp = requests.get(
            USER,
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
        resp = requests.request(
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
        accounts = self._request("GET", ACCOUNTS)
        result = []
        self._config.accounts = []
        for account in accounts:
            account_obj = Account.parse_obj(account)
            result.append(account_obj)
            self._config.accounts.append(account_obj)
        self._config.save()
        return result

    def zones(self) -> List[Zone]:
        zones = self._request("GET", ZONES)
        if self._config.accounts is None:
            self._config.accounts = []
        self._config.zones = []
        result = []
        for zone in zones:
            zone_obj = Zone.parse_obj(zone)
            result.append(zone_obj)
            self._config.zones.append(zone_obj)
        self._config.save()
        return result

    def kbs(self, account: str):
        path = LIST_KBS.format(account=account)
        try:
            kbs = self._request("GET", path)
        except UserTokenExpired:
            return []
        result = []
        zones = self.zones()
        region = {zone.id: zone.slug for zone in zones}
        for kb in kbs:
            zone = region[kb["zone"]]
            url = f"https://{zone}.{BASE_DOMAIN}/api/v1/kb/{kb['id']}"
            kb_obj = KnowledgeBox(
                url=url, id=kb["id"], title=kb["title"], account=account, region=zone
            )
            result.append(kb_obj)
        return result
