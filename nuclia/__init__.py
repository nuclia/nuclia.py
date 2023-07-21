import os

BASE_DOMAIN = os.environ.get("BASE_NUCLIA_DOMAIN", "nuclia.cloud")
BASE = f"https://{BASE_DOMAIN}"
REGIONAL = "https://{region}." + BASE_DOMAIN
CLOUD_ID = BASE.split("/")[-1]


def get_global_url(path: str):
    return BASE + path


def get_regional_url(region: str, path: str):
    return REGIONAL.format(region=region) + path
