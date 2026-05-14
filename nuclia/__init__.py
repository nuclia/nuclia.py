import os
from typing import List, Optional
from urllib.parse import urlparse

from nuclia.urls import (
    _regional_template,
    _root_domain,
    get_global_base,
    get_oauth_base,
    get_regional_base,
)

BASE_DOMAIN = os.environ.get("BASE_NUCLIA_DOMAIN", "progress.cloud")
CLOUD_ID = BASE_DOMAIN

REGIONAL = _regional_template(BASE_DOMAIN)
OAUTH_BASE = get_oauth_base(BASE_DOMAIN)
GLOBAL_BASE = get_global_base(BASE_DOMAIN)


def get_global_url(path: str):
    return GLOBAL_BASE + path


def get_regional_url(region: str, path: str, origin_url: Optional[str] = None):
    if origin_url:
        base = origin_url
    else:
        base = REGIONAL.format(region=(region or "").strip())
    return base.rstrip("/") + path


def get_oauth_base_url() -> str:
    return OAUTH_BASE


def get_list_parameter(param: Optional[List[str]]) -> List[str]:
    param = list(param or [])
    if len(param) > 0 and all([len(el) == 1 for el in param]):
        # Python Fire converts single string to list of chars
        param = ["".join(param)]
    return param


def is_nuclia_hosted(url: str):
    return _root_domain(BASE_DOMAIN) in urlparse(url).netloc


__all__ = [
    "BASE_DOMAIN",
    "CLOUD_ID",
    "REGIONAL",
    "OAUTH_BASE",
    "GLOBAL_BASE",
    "get_global_url",
    "get_regional_url",
    "get_oauth_base_url",
    "get_list_parameter",
    "is_nuclia_hosted",
    # urls.py helpers re-exported for convenience
    "_root_domain",
    "_regional_template",
    "get_global_base",
    "get_oauth_base",
    "get_regional_base",
]


# HACK used to debug in CI. Remove once the issue is solved

_DEBUG_HTTPX_REQUESTS = os.environ.get("DEBUG_HTTPX_REQUESTS", "false").lower() in {
    "true",
    "1",
}

if _DEBUG_HTTPX_REQUESTS:
    import httpx
    from wrapt import wrap_function_wrapper  # type: ignore

    def sync_wrapper(wrapped, instance: httpx.HTTPTransport, args, kwargs):
        print(f"[httpx::handle_request] {args[0].method} {args[0].url}")
        return wrapped(*args, **kwargs)

    async def async_wrapper(wrapped, instance: httpx.AsyncHTTPTransport, args, kwargs):
        print(f"[httpx::handle_async_request] {args[0].method} {args[0].url}")
        return await wrapped(*args, **kwargs)

    wrap_function_wrapper("httpx", "HTTPTransport.handle_request", sync_wrapper)
    wrap_function_wrapper(
        "httpx", "AsyncHTTPTransport.handle_async_request", async_wrapper
    )
