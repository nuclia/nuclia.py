import base64
from dataclasses import dataclass
from io import BytesIO
from typing import List, Optional, Union

from nucliadb_models.search import (
    ChatRequest,
    Filter,
    FindRequest,
    KnowledgeboxFindResults,
    Relations,
    SearchOptions,
    SearchRequest,
)

from nuclia.data import get_async_auth, get_auth
from nuclia.decorators import kb, pretty
from nuclia.lib.kb import AsyncNucliaDBClient, NucliaDBClient
from nuclia.sdk.auth import AsyncNucliaAuth, NucliaAuth


@dataclass
class ChatAnswer:
    answer: bytes
    learning_id: str
    relations_result: Optional[Relations]
    find_result: Optional[KnowledgeboxFindResults]

    def __str__(self):
        return self.answer.decode()


class NucliaSearch:
    """
    Perform search on a Knowledge Box.

    `find` and `search` accept the following parameters:
    - `json`: return results in JSON format
    - `yaml`: return results in YAML format
    """

    @property
    def _auth(self) -> NucliaAuth:
        auth = get_auth()
        return auth

    @kb
    @pretty
    def search(
        self,
        *,
        query: Union[str, SearchRequest] = "",
        filters: Optional[Union[List[str], List[Filter]]] = None,
        **kwargs,
    ):
        """
        Perform a search query.

        See https://docs.nuclia.dev/docs/api#tag/Search/operation/Search_Knowledge_Box_kb__kbid__search_post
        """
        ndb: AsyncNucliaDBClient = kwargs["ndb"]
        if isinstance(query, str):
            req = SearchRequest(query=query, filters=(filters or []))  # type: ignore
        else:
            req = query

        return ndb.ndb.search(req, kbid=ndb.kbid)

    @kb
    @pretty
    def find(
        self,
        *,
        query: Union[str, FindRequest] = "",
        highlight: Optional[bool] = False,
        relations: Optional[bool] = False,
        filters: Optional[Union[List[str], List[Filter]]] = None,
        **kwargs,
    ):
        """
        Perform a find query.

        See https://docs.nuclia.dev/docs/api#tag/Search/operation/Find_Knowledge_Box_kb__kbid__find_post
        """
        ndb: NucliaDBClient = kwargs["ndb"]
        if isinstance(query, str) and highlight is not None:
            req = FindRequest(
                query=query,
                highlight=highlight,
                filters=filters or [],  # type: ignore
            )
        elif isinstance(query, FindRequest):
            req = query
        else:
            raise Exception("Invalid Query either str or FindRequest")

        if relations:
            req.features.append(SearchOptions.RELATIONS)

        return ndb.ndb.find(req, kbid=ndb.kbid)

    @kb
    def chat(
        self,
        *,
        query: Union[str, ChatRequest],
        filters: Optional[Union[List[str], List[Filter]]] = None,
        **kwargs,
    ):
        """
        Answer a question.

        See https://docs.nuclia.dev/docs/api#tag/Search/operation/Chat_Knowledge_Box_kb__kbid__chat_post
        """
        ndb: NucliaDBClient = kwargs["ndb"]
        if isinstance(query, str):
            req = ChatRequest(
                query=query,
                filters=filters or [],  # type: ignore
            )
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


class AsyncNucliaSearch:
    """
    Perform search on a Knowledge Box.

    `find` and `search` accept the following parameters:
    - `json`: return results in JSON format
    - `yaml`: return results in YAML format
    """

    @property
    def _auth(self) -> AsyncNucliaAuth:
        auth = get_async_auth()
        return auth

    @kb
    @pretty
    async def search(
        self,
        *,
        query: Union[str, SearchRequest] = "",
        filters: Optional[List[str]] = None,
        **kwargs,
    ):
        """
        Perform a search query.

        See https://docs.nuclia.dev/docs/api#tag/Search/operation/Search_Knowledge_Box_kb__kbid__search_post
        """
        ndb: NucliaDBClient = kwargs["ndb"]
        if isinstance(query, str):
            req = SearchRequest(query=query, filters=(filters or []))
        else:
            req = query

        return await ndb.ndb.search(req, kbid=ndb.kbid)

    @kb
    @pretty
    async def find(
        self,
        *,
        query: Union[str, FindRequest] = "",
        highlight: Optional[bool] = False,
        relations: Optional[bool] = False,
        filters: Optional[List[str]] = None,
        **kwargs,
    ) -> KnowledgeboxFindResults:
        """
        Perform a find query.

        See https://docs.nuclia.dev/docs/api#tag/Search/operation/Find_Knowledge_Box_kb__kbid__find_post
        """

        ndb: AsyncNucliaDBClient = kwargs["ndb"]
        if isinstance(query, str) and highlight is not None:
            req = FindRequest(query=query, highlight=highlight, filters=(filters or []))
        elif isinstance(query, FindRequest):
            req = query
        else:
            raise Exception("Invalid Query either str or FindRequest")

        if relations:
            req.features.append(SearchOptions.RELATIONS)

        return await ndb.ndb.find(req, kbid=ndb.kbid)

    @kb
    async def chat(
        self,
        *,
        query: Union[str, ChatRequest],
        filters: Optional[List[str]] = None,
        **kwargs,
    ):
        """
        Answer a question.

        See https://docs.nuclia.dev/docs/api#tag/Search/operation/Chat_Knowledge_Box_kb__kbid__chat_post
        """
        ndb: AsyncNucliaDBClient = kwargs["ndb"]
        if isinstance(query, str):
            req = ChatRequest(query=query, filters=(filters or []))
        else:
            req = query

        content = b""
        response = await ndb.chat(req)

        content = await response.aread()
        stream = BytesIO(content)
        header = stream.read(4)
        payload_size = int.from_bytes(header, byteorder="big", signed=False)
        data = stream.read(payload_size)

        find_result = KnowledgeboxFindResults.parse_raw(base64.b64decode(data))

        data = stream.read()
        answer, relations_payload = data.split(b"_END_")

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
