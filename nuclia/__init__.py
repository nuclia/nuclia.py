import os
from typing import List, Optional
from urllib.parse import urlparse

BASE_DOMAIN = os.environ.get("BASE_NUCLIA_DOMAIN", "nuclia.cloud")
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
