from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Optional

from nuclia.exceptions import KBNotAvailable
from nuclia.lib.kb import AsyncNucliaDBClient, Environment, NucliaDBClient
from nuclia.config import read_config
from nuclia.sdk.auth import NucliaAuth
from nuclia.sdk.auth import AsyncNucliaAuth

if TYPE_CHECKING:
    from nuclia.config import Config
    from nuclia.sdk.auth import AsyncNucliaAuth, NucliaAuth


@dataclass
class DataConfig:
    config: Optional[Config] = None
    auth: Optional[NucliaAuth] = None
    async_auth: Optional[AsyncNucliaAuth] = None


DATA = DataConfig()


def set_config(config: Config):
    DATA.config = config


def get_config(config_path: Optional[str] = None) -> Config:
    if DATA.config is None or DATA.config.filepath != config_path:
        DATA.config = read_config(config_path=config_path)
    return DATA.config


def get_auth(config_path: Optional[str] = None) -> NucliaAuth:
    get_config(config_path=config_path)
    if config_path is not None:
        DATA.auth = NucliaAuth(config_path=config_path)
        return DATA.auth

    if DATA.auth is None:
        DATA.auth = NucliaAuth()
    return DATA.auth


def get_async_auth(config_path: Optional[str] = None) -> AsyncNucliaAuth:
    get_config(config_path=config_path)
    if config_path is not None:
        return AsyncNucliaAuth(config_path=config_path)

    if DATA.async_auth is None:
        DATA.async_auth = AsyncNucliaAuth()
    return DATA.async_auth


def get_client(kbid: str, config_path: Optional[str] = None) -> NucliaDBClient:
    auth = get_auth(config_path=config_path)
    kb_obj = auth._config.get_kb(kbid)

    if kb_obj is None:
        raise KBNotAvailable(kbid)
    elif kb_obj.region is None:
        # OSS
        ndb = NucliaDBClient(environment=Environment.OSS, url=kb_obj.url)
    else:
        if kb_obj.token is None and auth._validate_user_token():
            # User token auth
            ndb = NucliaDBClient(
                environment=Environment.CLOUD,
                url=kb_obj.url,
                user_token=auth._config.token,
                region=kb_obj.region,
            )
        elif kb_obj.token is None:
            # Public
            ndb = NucliaDBClient(
                environment=Environment.CLOUD,
                url=kb_obj.url,
                region=kb_obj.region,
            )
        else:
            ndb = NucliaDBClient(
                environment=Environment.CLOUD,
                url=kb_obj.url,
                api_key=kb_obj.token,
                region=kb_obj.region,
            )
    return ndb


async def get_async_client(kbid: str) -> AsyncNucliaDBClient:
    auth = get_async_auth()
    kb_obj = auth._config.get_kb(kbid)

    if kb_obj is None:
        raise KBNotAvailable(kbid)
    elif kb_obj.region is None:
        # OSS
        ndb = AsyncNucliaDBClient(environment=Environment.OSS, url=kb_obj.url)
    else:
        if kb_obj.token is None and await auth._validate_user_token():
            # User token auth
            ndb = AsyncNucliaDBClient(
                environment=Environment.CLOUD,
                url=kb_obj.url,
                user_token=auth._config.token,
                region=kb_obj.region,
            )
        elif kb_obj.token is None:
            # Public
            ndb = AsyncNucliaDBClient(
                environment=Environment.CLOUD,
                url=kb_obj.url,
                region=kb_obj.region,
            )
        else:
            ndb = AsyncNucliaDBClient(
                environment=Environment.CLOUD,
                url=kb_obj.url,
                api_key=kb_obj.token,
                region=kb_obj.region,
            )
    return ndb
