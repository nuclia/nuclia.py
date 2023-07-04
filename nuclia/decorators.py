import yaml

from functools import wraps
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
                if kb_obj.token is None:
                    # User token auth
                    ndb = NucliaDBClient(
                        environment=Environment.CLOUD,
                        url=kb_obj.url,
                        user_token=auth._config.token,
                        region=kb_obj.region,
                    )
                else:
                    ndb = NucliaDBClient(
                        environment=Environment.CLOUD,
                        url=kb_obj.url,
                        api_key=kb_obj.token,
                        region=kb_obj.region,
                    )

        elif url.find("nuclia.cloud") >= 0:
            ndb = NucliaDBClient(
                environment=Environment.CLOUD, url=url, api_key=api_key
            )
        else:
            ndb = NucliaDBClient(environment=Environment.OSS, url=url)
        kwargs["ndb"] = ndb
        return func(*args, **kwargs)

    return wrapper_checkout_kb


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

def pretty(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        result = func(*args, **kwargs)
        if kwargs.get("indent"):
            return result.json(indent=kwargs.get("indent"))
        if kwargs.get("yaml"):
            return yaml.dump(result)
        return result.json()

    return wrapper
