import base64
from dataclasses import dataclass
from enum import Enum
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

from nuclia.data import get_auth
from nuclia.decorators import kb, pretty
from nuclia.lib.kb import NucliaDBClient
from nuclia.sdk.auth import NucliaAuth


class FiltersOperator(str, Enum):
    ALL = "all"
    ANY = "any"
    NONE = "none"
    NOT_ALL = "not_all"


def _parse_filters(
    filters: Optional[List[str]], operator: str
) -> Union[list[str], list[Filter]]:
    if filters is None:
        return []
    try:
        operator_type = FiltersOperator(operator.lower())
    except ValueError:
        raise ValueError(
            f"Invalid operator {operator}. Must be one of {', '.join(FiltersOperator)}"
        )
    if operator_type == FiltersOperator.ALL:
        # We do not use the `all` operator on purpose to have more backward compatibility with
        # previous versions of the NucliaDB API.
        # The `all` operator is implicit when no operator is specified.
        return filters
    return [Filter.parse_obj({operator_type.value: filters})]


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
        filters: Optional[List[str]] = None,
        filters_operator: str = FiltersOperator.ALL.value,
        **kwargs,
    ):
        """
        Perform a search query.

        See https://docs.nuclia.dev/docs/api#tag/Search/operation/Search_Knowledge_Box_kb__kbid__search_post
        """
        ndb: NucliaDBClient = kwargs["ndb"]
        if isinstance(query, str):
            req = SearchRequest(
                query=query, filters=_parse_filters(filters, filters_operator)
            )
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
        filters: Optional[List[str]] = None,
        filters_operator: str = FiltersOperator.ALL.value,
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
                filters=_parse_filters(filters, filters_operator),
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
        filters: Optional[List[str]] = None,
        filters_operator: str = FiltersOperator.ALL.value,
        **kwargs,
    ):
        """
        Answer a question.

        See https://docs.nuclia.dev/docs/api#tag/Search/operation/Chat_Knowledge_Box_kb__kbid__chat_post
        """
        ndb: NucliaDBClient = kwargs["ndb"]
        if isinstance(query, str):
            req = ChatRequest(
                query=query, filters=_parse_filters(filters, filters_operator)
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
