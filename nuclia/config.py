from pydantic import BaseModel
from typing import List
import os


class KnowledgeBox(BaseModel):
    id: str
    title: str
    token: str


class NuaKey(BaseModel):
    id: str
    token: str


class Account(BaseModel):
    id: str
    title: str
    kbs: List[KnowledgeBox]
    nuas: List[NuaKey]


class Config(BaseModel):
    accounts: List[Account]
    user: str


CONFIG_DIR = "~/.nuclia"
CONFIG_PATH = CONFIG_DIR + "/config"


def read_config():
    if not os.path.exists(os.path.expanduser(CONFIG_PATH)):
        os.makedirs(os.path.expanduser(CONFIG_DIR), exist_ok=True)
        data = Config()
        with open(os.path.expanduser(CONFIG_PATH), "w") as config:
            config.write(data.json())

    with open(os.path.expanduser(CONFIG_PATH), "r") as config:
        config = Config.parse_raw(config.read())
    return config
