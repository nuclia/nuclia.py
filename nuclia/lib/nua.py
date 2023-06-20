from typing import Optional

import requests

from nuclia import REGIONAL
from nuclia.exceptions import NuaAPIException

SENTENCE_PREDICT = "/api/v1/predict/sentence"


class NuaClient:
    def __init__(self, region: str, account: str, token: str):
        self.region = region
        self.account = account
        self.token = token
        self.url = REGIONAL.format(region=region).strip("/")
        self.headers = {"X-STF-NUAKEY": f"Bearer {token}"}

    def sentence_predict(self, text: str, model: Optional[str] = None):
        resp = requests.get(
            f"{self.url}{SENTENCE_PREDICT}?query={text}&model={model}",
            headers=self.headers,
        )
        if resp.status_code == 200:
            return resp.json()
        else:
            raise NuaAPIException()