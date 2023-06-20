import os
from typing import List, Optional

from pydantic import BaseModel

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
        return f"{self.id:36} -> {'(' + self.account + ')' if self.account else ''} {self.title}"


class NuaKey(BaseModel):
    client_id: str
    title: Optional[str]
    region: str
    account: str
    token: str

    def __str__(self):
        return f"{self.client_id} {self.account} {self.title:30}"


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
                filter(lambda x: x.id == kbid, self.kbs if self.kbs is not None else [])
            )
        except StopIteration:
            kb_obj = next(
                filter(
                    lambda x: x.id == kbid,
                    self.kbs_token if self.kbs_token is not None else [],
                )
            )
        return kb_obj

    def set_user_token(self, code: str):
        self.token = code

    def set_nua_token(
        self,
        client_id: str,
        account: str,
        region: str,
        token: str,
        title: Optional[str] = None,
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
                title=title,
                account=account,
                region=region,
                token=token,
                client_id=client_id,
            )
        )
        self.save()

    def set_kb_token(
        self, url: str, token: str, kbid: str, title: Optional[str] = None
    ):
        try:
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

        kb_obj = KnowledgeBox(id=kbid, url=url, token=token, title=title)
        self.kbs_token.append(kb_obj)

        if yes_no(f"Do you want to setup KB {url} as default one?"):
            if self.default is None:
                self.default = Selection()
            self.default.kbid = kbid
        self.save()

    def get_default_kb(self) -> str:
        if self.default is None or self.default.kbid is None:
            raise NotDefinedDefault()
        return self.default.kbid

    def get_default_nua(self) -> str:
        if self.default is None or self.default.nua is None:
            raise NotDefinedDefault()
        return self.default.nua

    def set_default_nua(self, nua: str):
        if self.default is None:
            self.default = Selection()
        self.default.nua = nua
        self.save()

    def set_default_kb(self, kbid: str):
        if self.default is None:
            self.default = Selection()
        self.default.kbid = kbid
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
