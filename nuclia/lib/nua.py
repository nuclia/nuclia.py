from typing import Dict, List, Optional

import requests

from nuclia import REGIONAL
from nuclia.exceptions import NuaAPIException
from nuclia.lib.nua_responses import (
    ChatModel,
    Message,
    Sentence,
    Tokens,
    UserPrompt,
    SummarizeModel,
    SummarizeResource,
    Author,
)

SENTENCE_PREDICT = "/api/v1/predict/sentence"
CHAT_PREDICT = "/api/v1/predict/chat"
SUMMARIZE_PREDICT = "/api/v1/predict/summarize"
TOKENS_PREDICT = "/api/v1/predict/tokens"


class NuaClient:
    def __init__(self, region: str, account: str, token: str):
        self.region = region
        self.account = account
        self.token = token
        if "http" in region:
            self.url = region.strip("/")
        else:
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
            endpoint += f"?model={model}"

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

    def summarize(
        self, documents: Dict[str, str], model: Optional[str] = None
    ) -> bytes:
        endpoint = f"{self.url}{SUMMARIZE_PREDICT}"
        if model:
            endpoint += f"?model={model}"

        body = SummarizeModel(
            resources={
                key: SummarizeResource(fields={"field": document})
                for key, document in documents.items()
            }
        )
        resp = requests.post(
            endpoint, data=body.json(), headers=self.headers, stream=True
        )

        if resp.status_code == 200:
            return resp.content
        else:
            raise NuaAPIException()

    def generate_retrieval(
        self, question: str, context: List[str], model: Optional[str] = None
    ) -> bytes:
        endpoint = f"{self.url}{CHAT_PREDICT}"
        if model:
            endpoint += f"?model={model}"

        message_context = [
            Message(author=Author.USER, text=message) for message in context
        ]
        body = ChatModel(
            question=question,
            retrieval=True,
            user_id="Nuclia PY CLI",
            context=message_context,
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
