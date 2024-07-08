import json
from typing import Any, Dict, List, Optional, Union
from uuid import uuid4

from nucliadb_models.metadata import ResourceProcessingStatus
from nucliadb_models.resource import Resource
import os
from nuclia import get_list_parameter
from nuclia.decorators import kb, pretty
from nuclia.lib.kb import NucliaDBClient
from nuclia.sdk.logger import logger
from nucliadb_models.search import AskRequest, Filter
from pydantic import ValidationError

RESOURCE_ATTRIBUTES = [
    "icon",
    "origin",
    "extra",
    "conversations",
    "links",
    "texts",
    "files",
    "usermetadata",
    "fieldmetadata",
    "title",
    "summary",
    "metadata",
    "security",
]


class NucliaResource:
    """
    Manage existing resource

    All commands accept either `rid` or `slug` to identify the targeted resource.
    """

    @kb
    def create(*args, **kwargs) -> str:
        ndb = kwargs["ndb"]
        slug = kwargs.get("slug") or uuid4().hex
        kw = {
            "kbid": ndb.kbid,
            "slug": slug,
        }
        for param in RESOURCE_ATTRIBUTES:
            if param in kwargs:
                kw[param] = kwargs.get(param)
        resource = ndb.ndb.create_resource(**kw)
        rid = resource.uuid
        return rid

    @kb
    @pretty
    def ask(
        self,
        *,
        rid: Optional[str] = None,
        slug: Optional[str] = None,
        query: Union[str, dict, AskRequest],
        answer_json_schema: Optional[Dict[str, Any]] = None,
        answer_json_file: Optional[str] = None,
        filters: Optional[Union[List[str], List[Filter]]] = None,
        **kwargs,
    ):
        ndb: NucliaDBClient = kwargs["ndb"]

        if answer_json_file is not None:
            if os.path.exists(answer_json_file):
                with open(answer_json_file, "r") as json_file_handler:
                    answer_json_schema = json.load(json_file_handler)

        if isinstance(query, str):
            req = AskRequest(
                query=query,
                answer_json_schema=answer_json_schema,
            )
            if filters is not None:
                req.filters = filters
        elif isinstance(query, dict):
            try:
                req = AskRequest.model_validate(query)
            except ValidationError:
                raise ValueError("Invalid AskRequest object.")

        elif isinstance(query, AskRequest):
            req = query
        else:
            raise ValueError("Invalid query type. Must be str, dict or AskRequest.")

        if rid:
            res = ndb.ndb.ask_on_resource(
                req,
                kbid=ndb.kbid,
                rid=rid,
            )
        elif slug:
            res = ndb.ndb.ask_on_resource_by_slug(
                req,
                kbid=ndb.kbid,
                slug=slug,
            )
        else:
            raise ValueError("Either rid or slug must be provided")

        return res

    @kb
    @pretty
    def get(
        self,
        *,
        rid: Optional[str] = None,
        slug: Optional[str] = None,
        show: Optional[List[str]] = None,
        extracted: Optional[List[str]] = None,
        **kwargs,
    ) -> Resource:
        show = show or ["basic"]
        extracted = extracted or []
        ndb = kwargs["ndb"]
        show = get_list_parameter(show)
        extracted = get_list_parameter(extracted)
        if "basic" not in show:
            show.append("basic")
        if rid:
            res = ndb.ndb.get_resource_by_id(
                kbid=ndb.kbid,
                rid=rid,
                query_params={"show": show, "extracted": extracted},
            )
        elif slug:
            res = ndb.ndb.get_resource_by_slug(
                kbid=ndb.kbid,
                slug=slug,
                query_params={"show": show, "extracted": extracted},
            )
        else:
            raise ValueError("Either rid or slug must be provided")

        if (
            "extracted" in show
            and res.metadata.status != ResourceProcessingStatus.PROCESSED
        ):
            logger.warning(
                "Resource is not processed yet, extracted content may be empty or incomplete."
            )

        return res

    @kb
    def update(
        self, *, rid: Optional[str] = None, slug: Optional[str] = None, **kwargs
    ):
        ndb = kwargs["ndb"]
        kw = {
            "kbid": ndb.kbid,
        }
        for param in RESOURCE_ATTRIBUTES:
            if param in kwargs:
                kw[param] = kwargs.get(param)
        if rid:
            kw["rid"] = rid
            ndb.ndb.update_resource(**kw)
        elif slug:
            kw["rslug"] = slug
            ndb.ndb.update_resource_by_slug(**kw)
        else:
            raise ValueError("Either rid or slug must be provided")

    @kb
    def delete(
        self, *, rid: Optional[str] = None, slug: Optional[str] = None, **kwargs
    ):
        ndb = kwargs["ndb"]
        if rid:
            ndb.ndb.delete_resource(kbid=ndb.kbid, rid=rid)
        elif slug:
            ndb.ndb.delete_resource_by_slug(kbid=ndb.kbid, rslug=slug)
        else:
            raise ValueError("Either rid or slug must be provided")

    def _update_resource(self, rid: str, **kwargs):
        ndb = kwargs["ndb"]
        kw = {
            "kbid": ndb.kbid,
            "rid": rid,
        }
        for param in RESOURCE_ATTRIBUTES:
            if param in kwargs:
                kw[param] = kwargs.get(param)
        ndb.ndb.update_resource(**kw)


class AsyncNucliaResource:
    """
    Manage existing resource

    All commands accept either `rid` or `slug` to identify the targeted resource.
    """

    @kb
    async def create(*args, **kwargs) -> str:
        ndb = kwargs["ndb"]
        slug = kwargs.get("slug") or uuid4().hex
        kw = {
            "kbid": ndb.kbid,
            "slug": slug,
        }
        for param in RESOURCE_ATTRIBUTES:
            if param in kwargs:
                kw[param] = kwargs.get(param)
        resource = await ndb.ndb.create_resource(**kw)
        rid = resource.uuid
        return rid

    @kb
    @pretty
    async def get(
        self,
        *,
        rid: Optional[str] = None,
        slug: Optional[str] = None,
        show: Optional[List[str]] = None,
        extracted: Optional[List[str]] = None,
        **kwargs,
    ) -> Resource:
        show = show or ["basic"]
        extracted = extracted or []
        ndb = kwargs["ndb"]
        show = get_list_parameter(show)
        extracted = get_list_parameter(extracted)
        if "basic" not in show:
            show.append("basic")
        if rid:
            res = await ndb.ndb.get_resource_by_id(
                kbid=ndb.kbid,
                rid=rid,
                query_params={"show": show, "extracted": extracted},
            )
        elif slug:
            res = await ndb.ndb.get_resource_by_slug(
                kbid=ndb.kbid,
                slug=slug,
                query_params={"show": show, "extracted": extracted},
            )
        else:
            raise ValueError("Either rid or slug must be provided")

        if (
            "extracted" in show
            and res.metadata.status != ResourceProcessingStatus.PROCESSED
        ):
            logger.warning(
                "Resource is not processed yet, extracted content may be empty or incomplete."
            )

        return res

    @kb
    async def update(
        self, *, rid: Optional[str] = None, slug: Optional[str] = None, **kwargs
    ):
        ndb = kwargs["ndb"]
        if rid:
            await self._update_resource(kbid=ndb.kbid, rid=rid, **kwargs)
        elif slug:
            # TODO: delete directly when nucliadb sdk will support update by slug
            res = ndb.ndb.get_resource_by_slug(kbid=ndb.kbid, slug=slug)
            await self._update_resource(kbid=ndb.kbid, rid=res.id, **kwargs)
        else:
            raise ValueError("Either rid or slug must be provided")

    @kb
    async def delete(
        self, *, rid: Optional[str] = None, slug: Optional[str] = None, **kwargs
    ):
        ndb = kwargs["ndb"]
        if rid:
            await ndb.ndb.delete_resource(kbid=ndb.kbid, rid=rid)
        elif slug:
            # TODO: delete directly when nucliadb sdk will support delete by slug
            res = await ndb.ndb.get_resource_by_slug(kbid=ndb.kbid, slug=slug)
            await ndb.ndb.delete_resource(kbid=ndb.kbid, rid=res.id)
        else:
            raise ValueError("Either rid or slug must be provided")

    async def _update_resource(self, rid: str, **kwargs):
        ndb = kwargs["ndb"]
        kw = {
            "kbid": ndb.kbid,
            "rid": rid,
        }
        for param in RESOURCE_ATTRIBUTES:
            if param in kwargs:
                kw[param] = kwargs.get(param)
        await ndb.ndb.update_resource(**kw)
