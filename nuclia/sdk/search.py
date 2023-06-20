import base64
from dataclasses import dataclass
from typing import Optional, Union

from nucliadb_models.search import (
    ChatRequest,
    FindRequest,
    KnowledgeboxFindResults,
    Relations,
)

from nuclia.data import get_auth
from nuclia.decorators import kb
from nuclia.lib.kb import NucliaDBClient
from nuclia.sdk.auth import NucliaAuth


@dataclass
class ChatAnswer:
    answer: bytes
    learning_id: str
    relations_result: Optional[Relations]
    find_result: Optional[KnowledgeboxFindResults]

    def __str__(self):
        return self.answer.decode()


class NucliaSearch:
    @property
    def _auth(self) -> NucliaAuth:
        auth = get_auth()
        return auth

    @kb
    def find(self, *, ndb: NucliaDBClient, query: Union[str, FindRequest]):
        if isinstance(query, str):
            req = FindRequest(query=query)
        else:
            req = query

        return ndb.ndb.find(req, kbid=ndb.kbid)

    @kb
    def ask(self, *, ndb: NucliaDBClient, query: Union[str, ChatRequest]):
        if isinstance(query, str):
            req = ChatRequest(query=query)
        else:
            req = query
        response = ndb.chat(req)
        header = response.raw.read(4)
        payload_size = int.from_bytes(header, byteorder="big", signed=False)
        data = response.raw.read(payload_size)

        find_result = KnowledgeboxFindResults.parse_raw(base64.b64decode(data))

        data = response.raw.read()
        answer, relations_payload = data.split(b"_END_")

        relations_payload = response.raw.read()

        learning_id = response.headers.get("NUCLIA-LEARNING-ID")

        relations_result = None
        if len(relations_payload) > 0:
            relations_result = Relations.parse_raw(base64.b64decode(relations_payload))

        return ChatAnswer(
            answer=answer,
            learning_id=learning_id,
            relations_result=relations_result,
            find_result=find_result,
        )
