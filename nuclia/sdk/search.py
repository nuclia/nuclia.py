import json
import os
import warnings
from dataclasses import dataclass
from typing import Any, AsyncIterator, Dict, List, Optional, Union

from nucliadb_models.search import (
    AskRequest,
    AskResponseItem,
    CatalogRequest,
    Filter,
    FindRequest,
    KnowledgeboxFindResults,
    KnowledgeboxSearchResults,
    RagStrategies,
    RagImagesStrategies,
    Relations,
    FindOptions,
    SearchRequest,
    SyncAskResponse,
    ChatModel,
)
from pydantic import ValidationError

from nuclia.data import get_async_auth, get_auth
from nuclia.decorators import kb, pretty
from nuclia.lib.kb import AsyncNucliaDBClient, NucliaDBClient
from nuclia.sdk.logger import logger
from nuclia.sdk.auth import AsyncNucliaAuth, NucliaAuth
from nuclia.sdk.resource import RagImagesStrategiesParse, RagStrategiesParse


@dataclass
class AskAnswer:
    answer: bytes
    object: Optional[Dict[str, Any]]
    learning_id: str
    relations_result: Optional[Relations]
    find_result: Optional[KnowledgeboxFindResults]
    citations: Optional[Dict[str, Any]]
    prequeries: Optional[Dict[str, KnowledgeboxFindResults]]
    timings: Optional[Dict[str, float]]
    tokens: Optional[Dict[str, int]]
    retrieval_best_matches: Optional[List[str]]
    status: Optional[str]
    prompt_context: Optional[list[str]]
    relations: Optional[Relations]
    predict_request: Optional[ChatModel]
    error_details: Optional[str]

    def __str__(self):
        if self.answer:
            return self.answer.decode()
        if self.object:
            return json.dumps(self.object)
        return ""


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
    ) -> KnowledgeboxSearchResults:
        """
        Perform a search query.

        See https://docs.nuclia.dev/docs/api#tag/Search/operation/Search_Knowledge_Box_kb__kbid__search_post
        """
        ndb: NucliaDBClient = kwargs["ndb"]
        if isinstance(query, str):
            req = SearchRequest(query=query, filters=(filters or []), **kwargs)  # type: ignore
        elif isinstance(query, SearchRequest):
            req = query
        elif isinstance(query, dict):
            try:
                req = SearchRequest.model_validate(query)
            except ValidationError:
                logger.exception("Error validating query")
                raise
        else:
            raise Exception("Invalid Query either str or SearchRequest")

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
                **kwargs,
            )
        elif isinstance(query, FindRequest):
            req = query
        elif isinstance(query, dict):
            try:
                req = FindRequest.model_validate(query)
            except ValidationError:
                logger.exception("Error validating query")
                raise
        else:
            raise Exception("Invalid Query either str or FindRequest")

        if relations:
            req.features.append(FindOptions.RELATIONS)

        return ndb.ndb.find(req, kbid=ndb.kbid)

    @kb
    @pretty
    def catalog(
        self,
        *,
        query: Union[str, CatalogRequest] = "",
        filters: Optional[Union[List[str], List[Filter]]] = None,
        **kwargs,
    ):
        """
        Perform a catalog query.

        See https://docs.nuclia.dev/docs/api#tag/Search/operation/catalog_post_kb__kbid__catalog_post
        """
        ndb: NucliaDBClient = kwargs["ndb"]
        if isinstance(query, str):
            req = CatalogRequest(
                query=query,
                filters=filters or [],  # type: ignore
                **kwargs,
            )
        elif isinstance(query, CatalogRequest):
            req = query
        elif isinstance(query, dict):
            try:
                req = CatalogRequest.model_validate(query)
            except ValidationError:
                logger.exception("Error validating query")
                raise
        else:
            raise Exception("Invalid Query either str or CatalogRequest")

        return ndb.ndb.catalog(req, kbid=ndb.kbid)

    @kb
    def ask(
        self,
        *,
        query: Union[str, dict, AskRequest],
        filters: Optional[Union[List[str], List[Filter]]] = None,
        rag_strategies: Optional[list[RagStrategies]] = None,
        rag_images_strategies: Optional[list[RagImagesStrategies]] = None,
        **kwargs,
    ):
        """
        Answer a question.

        See https://docs.nuclia.dev/docs/api#tag/Search/operation/Ask_Knowledge_Box_kb__kbid__ask_post
        """
        ndb: NucliaDBClient = kwargs["ndb"]
        if isinstance(query, str):
            req = AskRequest(
                query=query,
                filters=filters or [],  # type: ignore
                **kwargs,
            )
            if rag_strategies is not None:
                req.rag_strategies = RagStrategiesParse.model_validate(
                    {"rag_strategies": rag_strategies}
                ).rag_strategies
            if rag_images_strategies is not None:
                req.rag_images_strategies = RagImagesStrategiesParse.model_validate(
                    {"rag_images_strategies": rag_images_strategies}
                ).rag_images_strategies
        elif isinstance(query, dict):
            try:
                req = AskRequest.model_validate(query)
            except ValidationError:
                logger.exception("Error validating query")
                raise
        elif isinstance(query, AskRequest):
            req = query
        else:
            raise ValueError("Invalid query type. Must be str, dict or AskRequest.")

        ask_response: SyncAskResponse = ndb.ndb.ask(kbid=ndb.kbid, content=req)

        result = AskAnswer(
            answer=ask_response.answer.encode(),
            learning_id=ask_response.learning_id,
            relations_result=ask_response.relations,
            find_result=ask_response.retrieval_results,
            prequeries=ask_response.prequeries,
            retrieval_best_matches=[
                best.id for best in ask_response.retrieval_best_matches
            ],
            citations=ask_response.citations,
            timings=None,
            tokens=None,
            object=ask_response.answer_json,
            status=ask_response.status,
            error_details=ask_response.error_details,
            predict_request=ChatModel.model_validate(ask_response.predict_request)
            if ask_response.predict_request is not None
            else None,
            relations=ask_response.relations,
            prompt_context=ask_response.prompt_context,
        )

        if ask_response.prompt_context:
            result.prompt_context = ask_response.prompt_context
        if ask_response.metadata is not None:
            if ask_response.metadata.timings is not None:
                result.timings = ask_response.metadata.timings.model_dump()
            if ask_response.metadata.tokens is not None:
                result.tokens = ask_response.metadata.tokens.model_dump()

        return result

    @kb
    def ask_json(
        self,
        schema: Union[str, Dict[str, Any]],
        query: Union[str, dict, AskRequest, None] = None,
        filters: Optional[Union[List[str], List[Filter]]] = None,
        **kwargs,
    ):
        """
        Answer a question.

        See https://docs.nuclia.dev/docs/api#tag/Search/operation/Ask_Knowledge_Box_kb__kbid__ask_post
        """
        ndb: NucliaDBClient = kwargs["ndb"]
        if isinstance(schema, str):
            if os.path.exists(schema):
                with open(schema, "r") as json_file_handler:
                    try:
                        schema_json = json.load(json_file_handler)
                    except Exception:
                        logger.exception("File format is not JSON")
                        return
            else:
                logger.exception("File not found")
                return
        else:
            schema_json = schema

        if isinstance(query, str):
            req = AskRequest(
                query=query,
                answer_json_schema=schema_json,
            )
            if filters is not None:
                req.filters = filters
        elif isinstance(query, dict):
            try:
                req = AskRequest.model_validate(query)
            except ValidationError:
                logger.exception("Error validating query")
                raise
        elif isinstance(query, AskRequest):
            req = query
        elif query is None:
            req = AskRequest(
                query="",
                answer_json_schema=schema_json,
            )
            if filters is not None:
                req.filters = filters
        else:
            raise ValueError("Invalid query type. Must be str, dict or AskRequest.")
        ask_response: SyncAskResponse = ndb.ndb.ask(kbid=ndb.kbid, content=req)

        result = AskAnswer(
            answer=ask_response.answer.encode(),
            learning_id=ask_response.learning_id,
            relations_result=ask_response.relations,
            find_result=ask_response.retrieval_results,
            prequeries=ask_response.prequeries,
            retrieval_best_matches=[
                best.id for best in ask_response.retrieval_best_matches
            ],
            citations=ask_response.citations,
            timings=None,
            tokens=None,
            object=ask_response.answer_json,
            status=ask_response.status,
            error_details=ask_response.error_details,
            predict_request=ChatModel.model_validate(ask_response.predict_request)
            if ask_response.predict_request is not None
            else None,
            relations=ask_response.relations,
            prompt_context=ask_response.prompt_context,
        )
        if ask_response.metadata is not None:
            if ask_response.metadata.timings is not None:
                result.timings = ask_response.metadata.timings.model_dump()
            if ask_response.metadata.tokens is not None:
                result.tokens = ask_response.metadata.tokens.model_dump()
        return result


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
        ndb: AsyncNucliaDBClient = kwargs["ndb"]
        if isinstance(query, str):
            req = SearchRequest(query=query, filters=(filters or []), **kwargs)  # type: ignore
        elif isinstance(query, SearchRequest):
            req = query
        elif isinstance(query, dict):
            try:
                req = SearchRequest.model_validate(query)
            except ValidationError:
                logger.exception("Error validating query")
                raise
        else:
            raise Exception("Invalid Query either str or SearchRequest")

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
            req = FindRequest(
                query=query, highlight=highlight, filters=(filters or []), **kwargs
            )
        elif isinstance(query, FindRequest):
            req = query
        elif isinstance(query, dict):
            try:
                req = FindRequest.model_validate(query)
            except ValidationError:
                logger.exception("Error validating query")
                raise
        else:
            raise Exception("Invalid Query either str or FindRequest")

        if relations:
            req.features.append(FindOptions.RELATIONS)

        return await ndb.ndb.find(req, kbid=ndb.kbid)

    @kb
    @pretty
    async def catalog(
        self,
        *,
        query: Union[str, CatalogRequest] = "",
        filters: Optional[Union[List[str], List[Filter]]] = None,
        **kwargs,
    ):
        """
        Perform a catalog query.

        See https://docs.nuclia.dev/docs/api#tag/Search/operation/catalog_post_kb__kbid__catalog_post
        """
        ndb: AsyncNucliaDBClient = kwargs["ndb"]
        if isinstance(query, str):
            req = CatalogRequest(
                query=query,
                filters=filters or [],  # type: ignore
                **kwargs,
            )
        elif isinstance(query, CatalogRequest):
            req = query
        elif isinstance(query, dict):
            try:
                req = CatalogRequest.model_validate(query)
            except ValidationError:
                logger.exception("Error validating query")
                raise
        else:
            raise Exception("Invalid Query either str or CatalogRequest")

        return await ndb.ndb.catalog(req, kbid=ndb.kbid)

    @kb
    async def ask(
        self,
        *,
        query: Union[str, dict, AskRequest],
        filters: Optional[List[str]] = None,
        timeout: int = 100,
        **kwargs,
    ):
        """
        Answer a question.

        See https://docs.nuclia.dev/docs/api#tag/Search/operation/Ask_Knowledge_Box_kb__kbid__ask_post
        """
        ndb: AsyncNucliaDBClient = kwargs["ndb"]

        if isinstance(query, str):
            req = AskRequest(
                query=query,
                filters=filters or [],  # type: ignore
                **kwargs,
            )
        elif isinstance(query, dict):
            try:
                req = AskRequest.model_validate(query)
            except ValidationError:
                logger.exception("Error validating query")
                raise
        elif isinstance(query, AskRequest):
            req = query
        else:
            raise ValueError("Invalid query type. Must be str, dict or AskRequest.")
        ask_stream_response = await ndb.ask(req, timeout=timeout)
        result = AskAnswer(
            answer=b"",
            learning_id=ask_stream_response.headers.get("NUCLIA-LEARNING-ID", ""),
            relations_result=None,
            find_result=None,
            prequeries=None,
            retrieval_best_matches=None,
            citations=None,
            timings=None,
            tokens=None,
            object=None,
            status=None,
            error_details=None,
            predict_request=None,
            relations=None,
            prompt_context=None,
        )
        async for line in ask_stream_response.aiter_lines():
            try:
                ask_response_item = AskResponseItem.model_validate_json(line).item
            except Exception as e:
                warnings.warn(f"Failed to parse AskResponseItem: {e}. item: {line}")
                continue
            if ask_response_item.type == "answer":
                result.answer += ask_response_item.text.encode()
            elif ask_response_item.type == "answer_json":
                result.object = ask_response_item.object
            elif ask_response_item.type == "retrieval":
                result.find_result = ask_response_item.results
            elif ask_response_item.type == "relations":
                result.relations_result = ask_response_item.relations
            elif ask_response_item.type == "citations":
                result.citations = ask_response_item.citations
            elif ask_response_item.type == "metadata":
                if ask_response_item.timings:
                    result.timings = ask_response_item.timings.model_dump()
                if ask_response_item.tokens:
                    result.tokens = ask_response_item.tokens.model_dump()
            elif ask_response_item.type == "status":
                result.status = ask_response_item.status
            elif ask_response_item.type == "prequeries":
                result.prequeries = ask_response_item.results
            elif ask_response_item.type == "error":
                result.error_details = ask_response_item.error
            elif ask_response_item.type == "debug":
                result.prompt_context = ask_response_item.metadata.get("prompt_context")
                result.predict_request = ask_response_item.metadata.get(
                    "predict_request"
                )
            else:  # pragma: no cover
                warnings.warn(f"Unknown ask stream item type: {ask_response_item.type}")
        return result

    @kb
    async def ask_stream(
        self,
        *,
        query: Union[str, dict, AskRequest],
        filters: Optional[List[str]] = None,
        timeout: int = 100,
        **kwargs,
    ) -> AsyncIterator[AskResponseItem]:
        """
        Answer a question.

        See https://docs.nuclia.dev/docs/api#tag/Search/operation/Ask_Knowledge_Box_kb__kbid__ask_post
        """
        ndb: AsyncNucliaDBClient = kwargs["ndb"]
        if isinstance(query, str):
            req = AskRequest(
                query=query,
                filters=filters or [],  # type: ignore
            )
        elif isinstance(query, dict):
            try:
                req = AskRequest.model_validate(query)
            except ValidationError:
                logger.exception("Error validating query")
                raise
        elif isinstance(query, AskRequest):
            req = query
        else:
            raise ValueError("Invalid query type. Must be str, dict or AskRequest.")
        ask_stream_response = await ndb.ask(req, timeout=timeout)
        async for line in ask_stream_response.aiter_lines():
            try:
                ask_response_item = AskResponseItem.model_validate_json(line)
            except Exception as e:
                warnings.warn(f"Failed to parse AskResponseItem: {e}. item: {line}")
                continue
            yield ask_response_item

    @kb
    async def ask_json(
        self,
        *,
        query: Union[str, dict, AskRequest],
        schema: Dict[str, Any],
        filters: Optional[List[str]] = None,
        timeout: int = 100,
        **kwargs,
    ):
        """
        Answer a question.

        See https://docs.nuclia.dev/docs/api#tag/Search/operation/Ask_Knowledge_Box_kb__kbid__ask_post
        """
        ndb: AsyncNucliaDBClient = kwargs["ndb"]

        if isinstance(query, str):
            req = AskRequest(
                query=query,
                answer_json_schema=schema,
                filters=filters or [],  # type: ignore
            )
        elif isinstance(query, dict):
            try:
                req = AskRequest.model_validate(query)
            except ValidationError:
                logger.exception("Error validating query")
                raise
        elif isinstance(query, AskRequest):
            req = query
        else:
            raise ValueError("Invalid query type. Must be str, dict or AskRequest.")
        ask_stream_response = await ndb.ask(req, timeout=timeout)
        result = AskAnswer(
            answer=b"",
            learning_id=ask_stream_response.headers.get("NUCLIA-LEARNING-ID", ""),
            relations_result=None,
            find_result=None,
            prequeries=None,
            retrieval_best_matches=None,
            citations=None,
            timings=None,
            tokens=None,
            object=None,
            status=None,
            error_details=None,
            predict_request=None,
            relations=None,
            prompt_context=None,
        )
        async for line in ask_stream_response.aiter_lines():
            try:
                ask_response_item = AskResponseItem.model_validate_json(line).item
            except Exception as e:
                warnings.warn(f"Failed to parse AskResponseItem: {e}. item: {line}")
                continue
            if ask_response_item.type == "answer":
                result.answer += ask_response_item.text.encode()
            elif ask_response_item.type == "retrieval":
                result.find_result = ask_response_item.results
            elif ask_response_item.type == "answer_json":
                result.object = ask_response_item.object
            elif ask_response_item.type == "relations":
                result.relations_result = ask_response_item.relations
            elif ask_response_item.type == "citations":
                result.citations = ask_response_item.citations
            elif ask_response_item.type == "metadata":
                if ask_response_item.timings:
                    result.timings = ask_response_item.timings.model_dump()
                if ask_response_item.tokens:
                    result.tokens = ask_response_item.tokens.model_dump()
            elif ask_response_item.type == "status":
                result.status = ask_response_item.status
            elif ask_response_item.type == "prequeries":
                result.prequeries = ask_response_item.results
            elif ask_response_item.type == "error":
                result.error_details = ask_response_item.error
            elif ask_response_item.type == "debug":
                result.prompt_context = ask_response_item.metadata.get("prompt_context")
                result.predict_request = ask_response_item.metadata.get(
                    "predict_request"
                )
            else:  # pragma: no cover
                warnings.warn(f"Unknown ask stream item type: {ask_response_item.type}")
        return result
