from typing import Dict, List, Optional
import webbrowser
import readline  # noqa
import requests
import jwt
from nuclia.cli.utils import yes_no
from nuclia.exceptions import NeedUserToken, UserTokenExpired

from nuclia.config import Account, Config, KnowledgeBox, Zone
from nuclia import BASE, get_global_url, get_regional_url

USER = f"{BASE}/api/v1/user/welcome"
MEMBER = f"{BASE}/api/v1/user"
ACCOUNTS = f"{BASE}/api/v1/accounts"
ZONES = f"{BASE}/api/v1/zones"
LIST_KBS = BASE + "/api/v1/account/{account}/kbs"


class NucliaAuth:
    _inner_config: Optional[Config] = None

    @property
    def _config(self) -> Config:
        if self._inner_config is None:
            from nuclia.data import get_config

            self._inner_config = get_config()
        return self._inner_config

    def kb(self, url: str, token: str):
        url = url.strip("/")
        if self.validate_kb(url, token):
            print("Validated")
            try:
                kbid = url.split("/")[-1]
                next(filter(lambda x: x.id == kbid, self._config.kbs))
                if yes_no(f"Want to replace actual KB {kbid} configuration") is False:
                    print("Cancelling operation")
                    return

            except StopIteration:
                # Not found
                pass

            self._config.set_kb_token(url, token)
        else:
            print("Invalid service token")

    def nua(self, token: str):
        if self.validate_nua(token):
            print("Validated")
            self._config.set_nua_token(token)
        else:
            print("Invalid service token")

    def validate_nua(self, region: str, token: str):
        # Validate the code is ok
        resp = requests.get(
            get_regional_url(region, f"/api/v1/kb/{kb}"),
            headers={"x-stf-nuakey", "Bearer {token}"},
        )
        if resp.status_code == 200:
            return True
        else:
            return False

    def validate_kb(self, url: str, token: str):
        # Validate the code is ok
        resp = requests.get(
            url,
            headers={"X-Nuclia-Serviceaccount", f"Bearer {token}"},
        )
        if resp.status_code == 200:
            return True
        else:
            return False

    def _show_user(self):
        print("Logged in!")
        resp: Dict[str, str] = self.get_user(MEMBER)
        print(f"User: {resp.get('name')} <{resp.get('email')}>")
        print(f"Type: {resp.get('type')}")

    def login(self):
        """
        Lets redirect the user to the UI to capture a token
        """
        if self._validate_user_token():
            self._show_user()
            return

        webbrowser.open(get_global_url("/redirect?display=token&ident={ident}"))
        code = input("Follow the browser flow and copy the token and paste it here:")
        print("Checking...")
        if self._validate_user_token(code):
            self._config.set_user_token(code)
            print("Auth completed!")
            self.post_login()
        else:
            print("Invalid token auth not completed")

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

    def post_user(self, path: str, payload: Dict[str, str]):
        if not self._config.token:
            raise NeedUserToken()
        resp = requests.post(
            path,
            headers={"Authorization": f"Bearer {self._config.token}"},
            data=payload,
        )
        if resp.status_code == 201:
            return resp.json()
        elif resp.status_code == 403:
            raise UserTokenExpired()

    def post_user(self, path: str, payload: Dict[str, str]):
        if not self._config.token:
            raise NeedUserToken()
        resp = requests.post(
            path,
            headers={"Authorization": f"Bearer {self._config.token}"},
            data=payload,
        )
        if resp.status_code == 201:
            return resp.json()
        elif resp.status_code == 403:
            raise UserTokenExpired()

    def get_user(self, path: str):
        if not self._config.token:
            raise NeedUserToken()
        resp = requests.get(
            path,
            headers={"Authorization": f"Bearer {self._config.token}"},
        )
        if resp.status_code == 200:
            return resp.json()
        elif resp.status_code == 403:
            raise UserTokenExpired()

    def accounts(self) -> List[Account]:
        accounts = self.get_user(ACCOUNTS)
        result = []
        self._config.accounts = []
        for account in accounts:
            account_obj = Account.parse_obj(account)
            result.append(account_obj)
            self._config.accounts.append(account_obj)
        self._config.save()
        return result

    def zones(self) -> List[Zone]:
        zones = self.get_user(ZONES)
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
            kbs = self.get_user(path)
        except UserTokenExpired:
            return []
        result = []
        zones = self.zones()
        region = {zone.id: zone.slug for zone in zones}
        for kb in kbs:
            zone = region[kb["zone"]]
            url = f"https://{zone}.nuclia.cloud/api/v1/kb/{kb['id']}"
            kb_obj = KnowledgeBox(
                url=url, id=kb["id"], title=kb["title"], account=account, region=zone
            )
            result.append(kb_obj)
        return result
