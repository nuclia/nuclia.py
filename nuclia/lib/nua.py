from typing import Optional

import requests

from nuclia import REGIONAL
from nuclia.exceptions import NuaAPIException
from nuclia.lib.nua_responses import ChatModel, Sentence, Tokens, UserPrompt

SENTENCE_PREDICT = "/api/v1/predict/sentence"
CHAT_PREDICT = "/api/v1/predict/chat"
TOKENS_PREDICT = "/api/v1/predict/tokens"


class NuaClient:
    def __init__(self, region: str, account: str, token: str):
        self.region = region
        self.account = account
        self.token = token
        self.url = REGIONAL.format(region=region).strip("/")
        self.headers = {"X-STF-NUAKEY": f"Bearer {token}"}

    def sentence_predict(self, text: str, model: Optional[str] = None) -> Sentence:
        endpoint = f"{self.url}{SENTENCE_PREDICT}?text={text}"
        if model:
            endpoint += f"&model={model}"
        resp = requests.get(endpoint, headers=self.headers)
        if resp.status_code == 200:
            return Sentence.parse_obj(resp.json())
        else:
            raise NuaAPIException()

    def tokens_predict(self, text: str, model: Optional[str] = None) -> Tokens:
        endpoint = f"{self.url}{TOKENS_PREDICT}?text={text}"
        if model:
            endpoint += f"&model={model}"
        resp = requests.get(endpoint, headers=self.headers)
        if resp.status_code == 200:
            return Tokens.parse_obj(resp.json())
        else:
            raise NuaAPIException()

    def generate_predict(self, text: str, model: Optional[str] = None) -> bytes:
        endpoint = f"{self.url}{CHAT_PREDICT}"
        if model:
            endpoint += f"model={model}"

        body = ChatModel(
            question="",
            retrieval=False,
            user_id="Nuclia PY CLI",
            user_prompt=UserPrompt(prompt=text),
        )
        resp = requests.post(
            endpoint, data=body.json(), headers=self.headers, stream=True
        )

        if resp.status_code == 200:
            response = b""
            for chunk in resp.raw.stream(1000, decode_content=True):
                response += chunk

            return response
        else:
            raise NuaAPIException()
