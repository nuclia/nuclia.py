from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from nuclia.cli.auth import NucliaAuth
    from nuclia.config import Config


@dataclass
class DataConfig:
    config: Optional[Config] = None
    auth: Optional[NucliaAuth] = None


DATA = DataConfig()


def set_config(config: Config):
    DATA.config = config


def get_config() -> Config:
    if DATA.config is None:
        from nuclia.config import read_config

        DATA.config = read_config()
    return DATA.config


def get_auth() -> NucliaAuth:
    get_config()
    if DATA.auth is None:
        from nuclia.cli.auth import NucliaAuth

        DATA.auth = NucliaAuth()
    return DATA.auth
