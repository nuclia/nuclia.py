import os

BASE = os.environ.get("BASE_NUCLIA_URL", "https://nuclia.cloud")
REGIONAL = "https://{region}.nuclia.cloud"
CLOUD_ID = BASE.split("/")[-1]


def get_global_url(path: str):
    return BASE + path


def get_regional_url(region: str, path: str):
    return REGIONAL.format(region=region) + path
