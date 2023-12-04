import base64
from time import sleep
from typing import Dict, List, Optional

import requests

from nuclia import REGIONAL
from nuclia.exceptions import NuaAPIException, AlreadyConsumed
from nuclia.lib.nua_responses import (
    Author,
    ChatModel,
    LearningConfig,
    Message,
    ProcessingStatus,
    PublicPushPayload,
    PublicPushResponse,
    PullResponse,
    PullStatus,
    Sentence,
    Source,
    SummarizedModel,
    SummarizeModel,
    SummarizeResource,
    Tokens,
    UserPrompt,
)

SENTENCE_PREDICT = "/api/v1/predict/sentence"
CHAT_PREDICT = "/api/v1/predict/chat"
SUMMARIZE_PREDICT = "/api/v1/predict/summarize"
TOKENS_PREDICT = "/api/v1/predict/tokens"
PUSH_PROCESS = "/api/v1/processing/push"
PULL_PROCESS = "/api/v1/processing/pull"
UPLOAD_PROCESS = "/api/v1/processing/upload"
STATUS_PROCESS = "/api/v1/processing/status"


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
            import pdb

            pdb.set_trace()
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
    ) -> SummarizedModel:
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
            return SummarizedModel.parse_raw(resp.content)
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

    def process_file(
        self, path: str, config: Optional[LearningConfig] = None
    ) -> PublicPushResponse:
        filename = path.split("/")[-1]
        upload_endpoint = f"{self.url}{UPLOAD_PROCESS}"

        headers = self.headers.copy()
        headers["X-FILENAME"] = base64.b64encode(filename.encode()).decode()
        with open(path, "rb") as file_to_upload:
            data = file_to_upload.read()

        resp = requests.post(upload_endpoint, data=data, headers=headers)

        # file_token =
        payload = PublicPushPayload(
            uuid=None, source=Source.HTTP, learning_config=config
        )
        payload.filefield[filename] = resp.content.decode()
        process_endpoint = f"{self.url}{PUSH_PROCESS}"
        resp = requests.post(
            process_endpoint, data=payload.json(), headers=self.headers
        )
        if resp.status_code == 200:
            return PublicPushResponse.parse_raw(resp.content)
        else:
            raise NuaAPIException()

    def wait_for_processing(self, request: PublicPushResponse) -> Optional[bytes]:
        status = self.processing_status()
        if (
            status.account is not None
            and request.account_seq is not None
            and status.account.last_delivered_seqid is not None
            and status.account.last_delivered_seqid >= request.account_seq
        ):
            raise AlreadyConsumed()

        collect_endpoint = f"{self.url}{PULL_PROCESS}"

        pull_resp = PullResponse(status=PullStatus.EMPTY, payload=None, msgid=None)
        count = 0
        while pull_resp.status == PullStatus.EMPTY and count < 10:
            resp = requests.get(collect_endpoint, headers=self.headers)
            # b'{"seqid":23257,"account_seq":1996,"queue":"private","uuid":"df8dd975-71e5-40d3-9470-7596a860f3f0"}'
            pull_resp = PullResponse.parse_raw(resp.content)
            count += 1
            if pull_resp.status == PullStatus.EMPTY:
                sleep(1)

        if pull_resp.payload is not None:
            return base64.b64decode(pull_resp.payload)
        else:
            return None

    def processing_status(self) -> ProcessingStatus:
        activity_endpoint = f"{self.url}{STATUS_PROCESS}"
        resp = requests.get(activity_endpoint, headers=self.headers)
        return ProcessingStatus.parse_raw(resp.content)
