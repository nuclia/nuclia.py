import os
from typing import List, Optional

from pydantic import BaseModel

from nuclia import CLOUD_ID
from nuclia.cli.utils import yes_no
from nuclia.exceptions import NotDefinedDefault

CONFIG_DIR = "~/.nuclia"
CONFIG_PATH = CONFIG_DIR + "/config"


class KnowledgeBox(BaseModel):
    id: str
    url: str
    title: Optional[str] = None
    slug: Optional[str] = None
    token: Optional[str] = None
    region: Optional[str] = None
    account: Optional[str] = None

    def __str__(self):
        return f"{self.id:36} -> {self.slug} {'(account: ' + self.account + ')' if self.account else ''}"


class NuaKey(BaseModel):
    client_id: str
    account_type: Optional[str]
    region: str
    account: str
    token: str

    def __str__(self):
        return f"{self.client_id} {self.account} {self.account_type:30}"


class Zone(BaseModel):
    id: str
    title: str
    slug: Optional[str] = None

    def __str__(self):
        return f"{self.id:30} - {self.slug}"


class Account(BaseModel):
    id: str
    title: str
    slug: Optional[str] = None

    def __str__(self):
        return f"{self.slug:15} => {self.title:40}"


class Selection(BaseModel):
    nua: Optional[str] = None
    kbid: Optional[str] = None
    account: Optional[str] = None
    nucliadb: Optional[str] = None
    zone: Optional[str] = None


class Config(BaseModel):
    accounts: Optional[List[Account]] = []
    kbs: Optional[List[KnowledgeBox]] = []
    kbs_token: List[KnowledgeBox] = []
    nuas_token: List[NuaKey] = []
    zones: Optional[List[Zone]] = []
    default: Optional[Selection] = Selection()
    user: Optional[str] = None
    token: Optional[str] = None

    def get_nua(self, nua_id: str) -> NuaKey:
        nua_obj = next(
            filter(
                lambda x: x.client_id == nua_id,
                self.nuas_token if self.nuas_token is not None else [],
            )
        )

        return nua_obj

    def get_kb(self, kbid: str) -> KnowledgeBox:
        try:
            kb_obj = next(
                filter(
                    lambda x: x.id == kbid,
                    self.kbs_token if self.kbs_token is not None else [],
                )
            )
        except StopIteration:
            kb_obj = next(
                filter(lambda x: x.id == kbid, self.kbs if self.kbs is not None else [])
            )
        return kb_obj

    def set_user_token(self, code: str):
        self.token = code

    def remove_user_token(self):
        self.token = None
        self.save()

    def set_nua_token(
        self,
        client_id: str,
        account: str,
        base_region: str,
        token: str,
        account_type: Optional[str] = None,
    ):
        if self.nuas_token is None:
            self.nuas_token = []
        try:
            nua_obj = next(filter(lambda x: x.client_id == client_id, self.nuas_token))
            self.nuas_token.remove(nua_obj)
        except StopIteration:
            pass

        self.nuas_token.append(
            NuaKey(
                account_type=account_type,
                account=account,
                region=base_region,
                token=token,
                client_id=client_id,
            )
        )
        self.save()

    def _del_kbid(self, kbid: str):
        try:
            while True:
                kb_obj = next(
                    filter(
                        lambda x: x.id == kbid,
                        self.kbs_token if self.kbs_token is not None else [],
                    )
                )
                if self.kbs_token is not None:
                    self.kbs_token.remove(kb_obj)
        except StopIteration:
            pass

    def set_kb_token(
        self,
        url: str,
        kbid: str,
        token: Optional[str] = None,
        title: Optional[str] = None,
        interactive: bool = True,
    ):
        self._del_kbid(kbid)
        region = (
            None
            if CLOUD_ID not in url
            else url.split(CLOUD_ID)[0].split("/")[-1].strip(".")
        )
        kb_obj = KnowledgeBox(id=kbid, url=url, token=token, title=title, region=region)
        self.kbs_token.append(kb_obj)

        if interactive is False or yes_no(
            f"Do you want to setup KB {url} as default one?"
        ):
            if self.default is None:
                self.default = Selection()
            self.default.kbid = kbid

        self.save()

    def get_default_nucliadb(self) -> Optional[str]:
        if self.default is None or self.default.nucliadb is None:
            raise NotDefinedDefault()
        return self.default.nucliadb

    def set_default_nucliadb(self, nucliadb: str):
        if self.default is None:
            self.default = Selection()
        self.default.nucliadb = nucliadb
        self.save()

    def get_default_nua(self) -> str:
        if self.default is None or self.default.nua is None:
            raise NotDefinedDefault()
        return self.default.nua

    def set_default_nua(self, nua: str):
        if self.default is None:
            self.default = Selection()
        self.default.nua = nua
        self.save()

    def get_default_account(self) -> str:
        if self.default is None or self.default.account is None:
            raise NotDefinedDefault()
        return self.default.account

    def set_default_account(self, account: str):
        if self.default is None:
            self.default = Selection()
        self.default.account = account
        self.save()

    def get_default_zone(self) -> Optional[str]:
        if self.default is None or self.default.zone is None:
            return None
        return self.default.zone

    def set_default_zone(self, zone: str):
        if self.default is None:
            self.default = Selection()
        self.default.zone = zone
        self.save()

    def get_default_kb(self) -> str:
        if self.default is None or self.default.kbid is None:
            raise NotDefinedDefault()
        return self.default.kbid

    def set_default_kb(self, kbid: str):
        if self.default is None:
            self.default = Selection()
        self.default.kbid = kbid
        self.save()

    def unset_default_kb(self, kbid: str):
        if self.default is None:
            self.default = Selection()
        if self.default.kbid == kbid:
            self.default.kbid = None
        self.save()

    def save(self):
        if not os.path.exists(os.path.expanduser(CONFIG_PATH)):
            os.makedirs(os.path.expanduser(CONFIG_DIR), exist_ok=True)

        from nuclia.data import DATA

        DATA.config = self
        with open(os.path.expanduser(CONFIG_PATH), "w") as config_file:
            config_file.write(self.json())


def read_config() -> Config:
    if not os.path.exists(os.path.expanduser(CONFIG_PATH)):
        os.makedirs(os.path.expanduser(CONFIG_DIR), exist_ok=True)
        config = Config()
        with open(os.path.expanduser(CONFIG_PATH), "w") as config_file:
            config_file.write(config.json())

    with open(os.path.expanduser(CONFIG_PATH), "r") as config_file:
        config = Config.parse_raw(config_file.read())

    if config.default is None:
        config.default = Selection()
    return config


def retrieve(kbs: List[KnowledgeBox], kb: str) -> Optional[KnowledgeBox]:
    kb_obj: Optional[KnowledgeBox] = None
    try:
        kb_obj = next(filter(lambda x: x.slug == kb, kbs))
    except StopIteration:
        try:
            kb_obj = next(filter(lambda x: x.id == kb, kbs))
        except StopIteration:
            pass
    return kb_obj


def retrieve_nua(nuas: List[NuaKey], nua: str) -> Optional[NuaKey]:
    nua_obj: Optional[NuaKey] = None
    try:
        nua_obj = next(filter(lambda x: x.client_id == nua, nuas))
    except StopIteration:
        pass
    return nua_obj


def retrieve_account(accounts: List[Account], account: str) -> Optional[Account]:
    account_obj: Optional[Account] = None
    try:
        account_obj = next(filter(lambda x: x.slug == account, accounts))
    except StopIteration:
        pass
    return account_obj


def set_config_file(path: str):
    global CONFIG_PATH
    CONFIG_PATH = path


def reset_config_file():
    global CONFIG_PATH
    CONFIG_PATH = CONFIG_DIR + "/config"
