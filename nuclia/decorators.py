import asyncio
from functools import wraps
import inspect

from httpx import ConnectError
import yaml

from nuclia import BASE_DOMAIN
from nuclia.data import get_async_auth, get_async_client, get_auth, get_client
from nuclia.exceptions import NotDefinedDefault, NucliaConnectionError
from nuclia.lib.kb import AsyncNucliaDBClient, Environment, NucliaDBClient
from nuclia.lib.nua import AsyncNuaClient, NuaClient


def accounts(func):
    @wraps(func)
    def wrapper_checkout_accounts(*args, **kwargs):
        auth = get_auth()
        auth.accounts()
        return func(*args, **kwargs)

    return wrapper_checkout_accounts


def kbs(func):
    @wraps(func)
    def wrapper_checkout_kbs(*args, **kwargs):
        if "account" in kwargs:
            auth = get_auth()
            account_id = auth.get_account_id(kwargs["account"])
            auth.kbs(account_id)
        return func(*args, **kwargs)

    return wrapper_checkout_kbs


def kb(func):
    @wraps(func)
    async def async_wrapper_checkout_kb(*args, **kwargs):
        if "ndb" in kwargs:
            return await func(*args, **kwargs)
        url = kwargs.get("url")
        api_key = kwargs.get("api_key")
        auth = get_async_auth()
        if url is None:
            # Get default KB
            kbid = auth._config.get_default_kb()
            if kbid is None:
                raise NotDefinedDefault()
            ndb = await get_async_client(kbid)
        elif url.find(BASE_DOMAIN) >= 0:
            region = url.split(".")[0].split("/")[-1]
            ndb = AsyncNucliaDBClient(
                environment=Environment.CLOUD, url=url, api_key=api_key, region=region
            )
        else:
            ndb = AsyncNucliaDBClient(environment=Environment.OSS, url=url)
        kwargs["ndb"] = ndb
        try:
            result = await func(*args, **kwargs)
            return result
        except ConnectError:
            raise NucliaConnectionError(f"Could not connect to {ndb}")

    @wraps(func)
    def wrapper_checkout_kb(*args, **kwargs):
        if "ndb" in kwargs:
            return func(*args, **kwargs)
        url = kwargs.get("url")
        api_key = kwargs.get("api_key")
        auth = get_auth()
        if url is None:
            # Get default KB
            kbid = auth._config.get_default_kb()
            if kbid is None:
                raise NotDefinedDefault()
            ndb = get_client(kbid)
        elif url.find(BASE_DOMAIN) >= 0:
            region = url.split(".")[0].split("/")[-1]
            ndb = NucliaDBClient(
                environment=Environment.CLOUD, url=url, api_key=api_key, region=region
            )
        else:
            ndb = NucliaDBClient(environment=Environment.OSS, url=url)
        kwargs["ndb"] = ndb
        try:
            result = func(*args, **kwargs)
            return result
        except ConnectError:
            raise NucliaConnectionError(f"Could not connect to {ndb}")

    if asyncio.iscoroutinefunction(func):
        return async_wrapper_checkout_kb
    else:
        return wrapper_checkout_kb


def nucliadb(func):
    @wraps(func)
    def wrapper_checkout_nucliadb(*args, **kwargs):
        if "ndb" in kwargs:
            return func(*args, **kwargs)
        url = kwargs.get("url")
        auth = get_auth()
        if url is None:
            # Get default KB
            nucliadb = auth._config.get_default_nucliadb()
            if nucliadb is None:
                raise NotDefinedDefault()
            # OSS
            ndb = NucliaDBClient(
                environment=Environment.OSS, base_url=f"{nucliadb}/api"
            )
        else:
            ndb = NucliaDBClient(environment=Environment.OSS, base_url=f"{url}/api")
        kwargs["ndb"] = ndb
        return func(*args, **kwargs)

    return wrapper_checkout_nucliadb


def nua(func):
    @wraps(func)
    async def async_wrapper_checkout_nua(*args, **kwargs):
        if "nc" in kwargs:
            return await func(*args, **kwargs)
        auth = get_auth()
        nua_id = auth._config.get_default_nua()
        if nua_id is None:
            raise NotDefinedDefault()

        nua_obj = auth._config.get_nua(nua_id)
        nc = AsyncNuaClient(
            region=nua_obj.region, account=nua_obj.account, token=nua_obj.token
        )

        kwargs["nc"] = nc
        return await func(*args, **kwargs)

    @wraps(func)
    async def async_generative_wrapper_checkout_nua(*args, **kwargs):
        if "nc" in kwargs:
            async for value in func(*args, **kwargs):
                yield value
        else:
            auth = get_auth()
            nua_id = auth._config.get_default_nua()
            if nua_id is None:
                raise NotDefinedDefault()

            nua_obj = auth._config.get_nua(nua_id)
            nc = AsyncNuaClient(
                region=nua_obj.region, account=nua_obj.account, token=nua_obj.token
            )

            kwargs["nc"] = nc
            async for value in func(*args, **kwargs):
                yield value

    @wraps(func)
    def wrapper_checkout_nua(*args, **kwargs):
        if "nc" in kwargs:
            return func(*args, **kwargs)

        auth = get_auth()
        nua_id = auth._config.get_default_nua()
        if nua_id is None:
            raise NotDefinedDefault()

        nua_obj = auth._config.get_nua(nua_id)
        nc = NuaClient(
            region=nua_obj.region, account=nua_obj.account, token=nua_obj.token
        )

        kwargs["nc"] = nc
        return func(*args, **kwargs)

    if inspect.isasyncgenfunction(func):
        return async_generative_wrapper_checkout_nua
    elif asyncio.iscoroutinefunction(func):
        return async_wrapper_checkout_nua
    else:
        return wrapper_checkout_nua


def account(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        account_slug = kwargs.get("account")
        account_id = kwargs.get("account_id")
        auth = get_auth()
        if account_id is None and account_slug is None:
            account_slug = auth._config.get_default_account()
            if account_slug is None:
                raise NotDefinedDefault()
            kwargs["account"] = account_slug
        if account_id is None:
            account_id = auth.get_account_id(account_slug)  # type: ignore
            kwargs["account_id"] = account_id
        return func(*args, **kwargs)

    return wrapper


def pretty(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        result = func(*args, **kwargs)
        if kwargs.get("json"):
            return result.json(indent=2)
        if kwargs.get("yaml"):
            return yaml.dump(result)
        return result

    @wraps(func)
    async def async_wrapper(*args, **kwargs):
        result = await func(*args, **kwargs)
        if kwargs.get("json"):
            return result.json(indent=2)
        if kwargs.get("yaml"):
            return yaml.dump(result)
        return result

    if asyncio.iscoroutinefunction(func):
        return async_wrapper
    else:
        return wrapper


def zone(func):
    @wraps(func)
    def wrapper_checkout_zone(*args, **kwargs):
        zone = kwargs.get("zone")
        if not zone:
            auth = get_auth()
            kwargs["zone"] = auth._config.get_default_zone()
        return func(*args, **kwargs)

    return wrapper_checkout_zone
