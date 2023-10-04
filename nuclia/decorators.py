from functools import wraps

import yaml

from nuclia import BASE_DOMAIN
from nuclia.data import get_auth
from nuclia.exceptions import NotDefinedDefault
from nuclia.lib.kb import Environment, NucliaDBClient
from nuclia.lib.nua import NuaClient


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
            auth.kbs(kwargs["account"])
        return func(*args, **kwargs)

    return wrapper_checkout_kbs


def kb(func):
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

            kb_obj = auth._config.get_kb(kbid)

            if kb_obj.region is None:
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

        elif url.find(BASE_DOMAIN) >= 0:
            region = url.split(".")[0].split("/")[-1]
            ndb = NucliaDBClient(
                environment=Environment.CLOUD, url=url, api_key=api_key, region=region
            )
        else:
            ndb = NucliaDBClient(environment=Environment.OSS, url=url)
        kwargs["ndb"] = ndb
        return func(*args, **kwargs)

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
    def wrapper_checkout_nua(*args, **kwargs):
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

    return wrapper_checkout_nua


def account(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        if not kwargs.get("account"):
            auth = get_auth()
            account_slug = auth._config.get_default_account()
            if account_slug is None:
                raise NotDefinedDefault()
            else:
                kwargs["account"] = account_slug
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

    return wrapper
