import os
from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel

from nuclia.cli.utils import yes_no

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
        return f"{self.account:20}: {self.id:36} -> {self.title}"


class NuaKey(BaseModel):
    client_id: str
    title: str
    zone: str
    created: datetime

    def __str__(self):
        return f"{self.client_id} {self.title:30} ({self.created})"


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
    nuas: Optional[List[NuaKey]] = []

    def __str__(self):
        return f"{self.slug:15} => {self.title:40}"


class Selection(BaseModel):
    account: Optional[str] = None
    kbid: Optional[str] = None


class Config(BaseModel):
    accounts: Optional[List[Account]] = []
    kbs: Optional[List[KnowledgeBox]] = []
    kbs_token: Optional[List[KnowledgeBox]] = []
    zones: Optional[List[Zone]] = []
    default: Optional[Selection] = None
    user: Optional[str]
    token: Optional[str]

    def get_kb(self, kbid: str) -> KnowledgeBox:
        try:
            kb_obj = next(filter(lambda x: x.id == kbid, self.kbs))
        except StopIteration:
            kb_obj = next(filter(lambda x: x.id == kbid, self.kbs_token))
        return kb_obj

    def set_user_token(self, code: str):
        self.token = code

    def set_nua_token(self, account: str, nua: str):
        raise NotImplementedError()

    def set_kb_token(self, url: str, token: str):
        kbid = url.split("/")[-1]
        try:
            kb_obj = next(filter(lambda x: x.id == kbid, self.kbs))
            self.kbs_token.remove(kb_obj)
        except StopIteration:
            pass

        kb_obj = KnowledgeBox(id=kbid, url=url, token=token)
        self.kbs_token.append(kb_obj)

        if yes_no("Do you want to setup KB {url} as default one?"):
            if self.default is None:
                self.default = Selection()
            self.default.kbid = kbid
        self.save()

    def get_default_kb(self) -> Selection:
        return self.default

    def set_default_kb(self, account: str, kbid: str) -> Selection:
        self.default.account = account
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
