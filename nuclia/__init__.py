import os
from typing import List, Optional
from urllib.parse import urlparse

BASE_DOMAIN = os.environ.get("BASE_NUCLIA_DOMAIN", "rag.progress.cloud")
BASE = f"https://{BASE_DOMAIN}"
REGIONAL = "https://{region}." + BASE_DOMAIN
CLOUD_ID = BASE.split("/")[-1]


def get_global_url(path: str):
    return BASE + path


def get_regional_url(region: str, path: str):
    return REGIONAL.format(region=region) + path


def get_list_parameter(param: Optional[List[str]]) -> List[str]:
    param = list(param or [])
    if len(param) > 0 and all([len(el) == 1 for el in param]):
        # Python Fire converts single string to list of chars
        param = ["".join(param)]
    return param


def is_nuclia_hosted(url: str):
    return BASE_DOMAIN in urlparse(url).netloc


# HACK used to debug in CI. Remove once the issue is solved

_DEBUG_HTTPX_REQUESTS = os.environ.get("DEBUG_HTTPX_REQUESTS", "false").lower() in {
    "true",
    "1",
}

if _DEBUG_HTTPX_REQUESTS:
    import httpx
    from wrapt import wrap_function_wrapper

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
