import base64
from typing import Dict, List, Optional
from time import sleep
import requests
from nucliadb_protos.writer_pb2 import BrokerMessage

from nuclia import REGIONAL
from nuclia.exceptions import NuaAPIException
from nuclia.lib.nua_responses import (
    ChatModel,
    ConfigSchema,
    LearningConfigurationCreation,
    LearningConfigurationUpdate,
    ProcessRequestStatus,
    ProcessRequestStatusResults,
    PushPayload,
    PushResponseV2,
    RestrictedIDString,
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
UPLOAD_PROCESS = "/api/v1/processing/upload"
STATUS_PROCESS = "/api/v2/processing/status"
PUSH_PROCESS = "/api/v2/processing/push"
SCHEMA = "/api/v1/learning/configuration/schema"
SCHEMA_KBID = "/api/v1/schema"


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

    def add_config_predict(self, kbid: str, config: LearningConfigurationCreation):
        endpoint = f"{self.url}{SCHEMA_KBID}/{kbid}"
        resp = requests.post(endpoint, json=config.dict(), headers=self.headers)
        if resp.status_code != 200:
            raise NuaAPIException(code=resp.status_code, detail=resp.content.decode())

    def update_config_predict(self, kbid: str, config: LearningConfigurationUpdate):
        endpoint = f"{self.url}{SCHEMA_KBID}/{kbid}"
        resp = requests.post(endpoint, json=config.dict(), headers=self.headers)
        if resp.status_code != 200:
            raise NuaAPIException(code=resp.status_code, detail=resp.content.decode())

    def schema_predict(self, kbid: Optional[str] = None) -> ConfigSchema:
        endpoint = f"{self.url}{SCHEMA}"
        if kbid is not None:
            endpoint = f"{self.url}{SCHEMA_KBID}/{kbid}"
        resp = requests.get(endpoint, headers=self.headers)
        if resp.status_code == 200:
            return ConfigSchema.parse_obj(resp.json())
        else:
            raise NuaAPIException(code=resp.status_code, detail=resp.content.decode())

    def sentence_predict(self, text: str, model: Optional[str] = None) -> Sentence:
        endpoint = f"{self.url}{SENTENCE_PREDICT}?text={text}"
        if model:
            endpoint += f"&model={model}"
        resp = requests.get(endpoint, headers=self.headers)
        if resp.status_code == 200:
            return Sentence.parse_obj(resp.json())
        else:
            raise NuaAPIException(code=resp.status_code, detail=resp.content.decode())

    def tokens_predict(self, text: str, model: Optional[str] = None) -> Tokens:
        endpoint = f"{self.url}{TOKENS_PREDICT}?text={text}"
        if model:
            endpoint += f"&model={model}"
        resp = requests.get(endpoint, headers=self.headers)
        if resp.status_code == 200:
            return Tokens.parse_obj(resp.json())
        else:
            raise NuaAPIException(code=resp.status_code, detail=resp.content.decode())

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
            raise NuaAPIException(code=resp.status_code, detail=resp.content.decode())

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
            raise NuaAPIException(code=resp.status_code, detail=resp.content.decode())

    def generate_retrieval(
        self,
        question: str,
        context: List[str],
        model: Optional[str] = None,
    ) -> bytes:
        endpoint = f"{self.url}{CHAT_PREDICT}"
        if model:
            endpoint += f"?model={model}"
        body = ChatModel(
            question=question,
            retrieval=True,
            user_id="Nuclia PY CLI",
            query_context=context,
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
            raise NuaAPIException(code=resp.status_code, detail=resp.content.decode())

    def process_file(self, path: str, kbid: Optional[str] = None) -> PushResponseV2:
        filename = path.split("/")[-1]
        upload_endpoint = f"{self.url}{UPLOAD_PROCESS}"

        headers = self.headers.copy()
        headers["X-FILENAME"] = base64.b64encode(filename.encode()).decode()
        with open(path, "rb") as file_to_upload:
            data = file_to_upload.read()

        resp = requests.post(upload_endpoint, data=data, headers=headers)

        payload = PushPayload(
            uuid=None, source=Source.HTTP, kbid=RestrictedIDString(kbid)
        )

        payload.filefield[filename] = resp.content.decode()
        process_endpoint = f"{self.url}{PUSH_PROCESS}"
        resp = requests.post(
            process_endpoint, data=payload.json(), headers=self.headers
        )
        if resp.status_code == 200:
            return PushResponseV2.parse_raw(resp.content)
        else:
            raise NuaAPIException(code=resp.status_code, detail=resp.content.decode())

    def wait_for_processing(
        self, response: PushResponseV2, timeout: int = 30
    ) -> Optional[BrokerMessage]:

        resp = self.processing_id_status(response.processing_id)
        count = timeout
        while resp.completed is False and resp.failed is False and count > 0:
            resp = self.processing_id_status(response.processing_id)
            sleep(3)
            count -= 1

        bm = None
        if resp.response:
            bm = BrokerMessage()
            bm.ParseFromString(base64.b64decode(resp.response))

        return bm

    def processing_status(self) -> ProcessRequestStatusResults:
        activity_endpoint = f"{self.url}{STATUS_PROCESS}"
        resp = requests.get(activity_endpoint, headers=self.headers)
        return ProcessRequestStatusResults.parse_raw(resp.content)

    def processing_id_status(self, process_id: str) -> ProcessRequestStatus:
        activity_endpoint = f"{self.url}{STATUS_PROCESS}/{process_id}"
        resp = requests.get(activity_endpoint, headers=self.headers)
        return ProcessRequestStatus.parse_raw(resp.content)
