from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Optional

from nuclia.exceptions import KBNotAvailable
from nuclia.lib.kb import AsyncNucliaDBClient, Environment, NucliaDBClient

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


def get_config() -> Config:
    if DATA.config is None:
        from nuclia.config import read_config

        DATA.config = read_config()
    return DATA.config


def get_auth() -> NucliaAuth:
    get_config()
    if DATA.auth is None:
        from nuclia.sdk.auth import NucliaAuth

        DATA.auth = NucliaAuth()
    return DATA.auth


def get_async_auth() -> AsyncNucliaAuth:
    get_config()
    if DATA.async_auth is None:
        from nuclia.sdk.auth import AsyncNucliaAuth

        DATA.async_auth = AsyncNucliaAuth()
    return DATA.async_auth


def get_client(kbid: str) -> NucliaDBClient:
    auth = get_auth()
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
