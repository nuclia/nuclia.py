import json
import os
from typing import Any, Dict, List, Optional, Union
from uuid import uuid4

import backoff
import requests
from nucliadb_models.metadata import ResourceProcessingStatus
from nucliadb_models.resource import Resource
from nucliadb_models.search import (
    AskRequest,
    Filter,
    RagImagesStrategies,
    RagStrategies,
)
from nucliadb_sdk.v2 import exceptions
from pydantic import BaseModel, Field, ValidationError

from nuclia import get_list_parameter, get_regional_url
from nuclia.data import get_async_auth, get_auth
from nuclia.decorators import kb, pretty
from nuclia.exceptions import RateLimitError
from nuclia.lib.kb import AsyncNucliaDBClient, NucliaDBClient
from nuclia.sdk.logger import logger

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
    "wait_for_commit",
]


class RagStrategiesParse(BaseModel):
    rag_strategies: list[RagStrategies] = Field(default=[])


class RagImagesStrategiesParse(BaseModel):
    rag_images_strategies: list[RagImagesStrategies] = Field(default=[])


class NucliaResource:
    """
    Manage existing resource

    All commands accept either `rid` or `slug` to identify the targeted resource.
    """

    @backoff.on_exception(
        backoff.expo,
        RateLimitError,
        jitter=backoff.random_jitter,
        max_tries=5,
        factor=10,
    )
    @kb
    def create(*args, **kwargs) -> str:
        ndb: NucliaDBClient = kwargs["ndb"]
        slug = kwargs.get("slug") or uuid4().hex
        kw = {
            "kbid": ndb.kbid,
            "slug": slug,
        }
        for param in RESOURCE_ATTRIBUTES:
            if param in kwargs:
                kw[param] = kwargs.get(param)
        try:
            resource = ndb.ndb.create_resource(**kw)
        except exceptions.RateLimitError as exc:
            logger.debug(
                "Rate limited while trying to create a resource. Waiting a bit before trying again..."
            )
            raise RateLimitError() from exc
        rid = resource.uuid
        return rid

    @kb
    @pretty
    def ask(
        self,
        *,
        rid: Optional[str] = None,
        slug: Optional[str] = None,
        query: Union[str, dict, AskRequest, None] = None,
        answer_json_schema: Optional[Dict[str, Any]] = None,
        answer_json_file: Optional[str] = None,
        filters: Optional[Union[List[str], List[Filter]]] = None,
        rag_strategies: Optional[list[RagStrategies]] = None,
        rag_images_strategies: Optional[list[RagImagesStrategies]] = None,
        **kwargs,
    ):
        ndb: NucliaDBClient = kwargs["ndb"]

        if query is None:
            query = ""

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
        ndb: NucliaDBClient = kwargs["ndb"]
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
    def download_file(
        self,
        *,
        rid: Optional[str] = None,
        slug: Optional[str] = None,
        file_id: str,
        output: str,
        **kwargs,
    ):
        ndb: NucliaDBClient = kwargs["ndb"]
        if rid:
            res = ndb.ndb.get_resource_by_id(
                kbid=ndb.kbid, rid=rid, query_params={"show": ["values"]}
            )
        elif slug:
            res = ndb.ndb.get_resource_by_slug(
                kbid=ndb.kbid, slug=slug, query_params={"show": ["values"]}
            )
        else:
            raise ValueError("Either rid or slug must be provided")
        file_field = res.data.files.get(file_id)
        if not file_field:
            raise ValueError(f"File with id {file_id} not found in resource")
        url = get_regional_url(ndb.region, "/api/v1" + file_field.value.file.uri)
        download = requests.get(url, stream=True, headers=ndb.headers)
        if download.status_code != 200:
            raise ValueError(f"Error downloading file: {download.text}")
        with open(output, "wb") as f:
            for chunk in download.iter_content(chunk_size=1024):
                if chunk:
                    f.write(chunk)

    @kb
    def temporal_download_url(
        self,
        *,
        rid: Optional[str] = None,
        slug: Optional[str] = None,
        file_id: str,
        ttl: int = 10,
        **kwargs,
    ):
        ndb = kwargs["ndb"]
        if rid:
            res = ndb.ndb.get_resource_by_id(
                kbid=ndb.kbid, rid=rid, query_params={"show": ["values"]}
            )
        elif slug:
            res = ndb.ndb.get_resource_by_slug(
                kbid=ndb.kbid, slug=slug, query_params={"show": ["values"]}
            )
        else:
            raise ValueError("Either rid or slug must be provided")
        file_field = res.data.files.get(file_id)
        if not file_field:
            raise ValueError(f"File with id {file_id} not found in resource")
        url = get_regional_url(ndb.region, "/api/v1" + file_field.value.file.uri)
        auth = get_auth()
        token = auth.create_ephemeral_token(ndb.kbid, ttl=ttl)
        return f"{url}?eph-token={token.token}"

    @kb
    def update(
        self, *, rid: Optional[str] = None, slug: Optional[str] = None, **kwargs
    ):
        ndb: NucliaDBClient = kwargs["ndb"]
        kw = {
            "kbid": ndb.kbid,
        }
        for param in RESOURCE_ATTRIBUTES:
            if param in kwargs:
                kw[param] = kwargs.get(param)  # type: ignore
        if rid:
            kw["rid"] = rid
            if slug:
                kw["slug"] = slug
            ndb.ndb.update_resource(**kw)
        elif slug:
            kw["rslug"] = slug
            ndb.ndb.update_resource_by_slug(**kw)
        else:
            raise ValueError("Either rid or slug must be provided")

    @kb
    def send_to_process(
        self, *, rid: Optional[str] = None, slug: Optional[str] = None, **kwargs
    ):
        ndb: NucliaDBClient = kwargs["ndb"]
        kw = {
            "kbid": ndb.kbid,
        }
        if rid:
            kw["rid"] = rid
            if slug:
                kw["slug"] = slug
            ndb.ndb.reprocess_resource(**kw)
        elif slug:
            kw["rslug"] = slug
            ndb.ndb.reprocess_resource_by_slug(**kw)
        else:
            raise ValueError("Either rid or slug must be provided")

    @kb
    def delete(
        self, *, rid: Optional[str] = None, slug: Optional[str] = None, **kwargs
    ):
        ndb: NucliaDBClient = kwargs["ndb"]
        if rid:
            ndb.ndb.delete_resource(kbid=ndb.kbid, rid=rid)
        elif slug:
            ndb.ndb.delete_resource_by_slug(kbid=ndb.kbid, rslug=slug)
        else:
            raise ValueError("Either rid or slug must be provided")


class AsyncNucliaResource:
    """
    Manage existing resource

    All commands accept either `rid` or `slug` to identify the targeted resource.
    """

    @kb
    async def create(*args, **kwargs) -> str:
        ndb: AsyncNucliaDBClient = kwargs["ndb"]
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
        ndb: AsyncNucliaDBClient = kwargs["ndb"]
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
    async def download_file(
        self,
        *,
        rid: Optional[str] = None,
        slug: Optional[str] = None,
        file_id: str,
        output: str,
        **kwargs,
    ):
        ndb: AsyncNucliaDBClient = kwargs["ndb"]
        if rid:
            res = await ndb.ndb.get_resource_by_id(
                kbid=ndb.kbid, rid=rid, query_params={"show": ["values"]}
            )
        elif slug:
            res = await ndb.ndb.get_resource_by_slug(
                kbid=ndb.kbid, slug=slug, query_params={"show": ["values"]}
            )
        else:
            raise ValueError("Either rid or slug must be provided")
        file_field = res.data.files.get(file_id)
        if not file_field:
            raise ValueError(f"File with id {file_id} not found in resource")
        url = get_regional_url(ndb.region, "/api/v1" + file_field.value.file.uri)
        download = requests.get(url, stream=True, headers=ndb.headers)
        if download.status_code != 200:
            raise ValueError(f"Error downloading file: {download.text}")
        with open(output, "wb") as f:
            for chunk in download.iter_content(chunk_size=1024):
                if chunk:
                    f.write(chunk)

    @kb
    async def temporal_download_url(
        self,
        *,
        rid: Optional[str] = None,
        slug: Optional[str] = None,
        file_id: str,
        ttl: int = 10,
        **kwargs,
    ):
        ndb = kwargs["ndb"]
        if rid:
            res = await ndb.ndb.get_resource_by_id(
                kbid=ndb.kbid, rid=rid, query_params={"show": ["values"]}
            )
        elif slug:
            res = await ndb.ndb.get_resource_by_slug(
                kbid=ndb.kbid, slug=slug, query_params={"show": ["values"]}
            )
        else:
            raise ValueError("Either rid or slug must be provided")
        file_field = res.data.files.get(file_id)
        if not file_field:
            raise ValueError(f"File with id {file_id} not found in resource")
        url = get_regional_url(ndb.region, "/api/v1" + file_field.value.file.uri)
        download = requests.get(url, stream=True, headers=ndb.headers)
        if download.status_code != 200:
            raise ValueError(f"Error downloading file: {download.text}")
        auth = get_async_auth()
        token = await auth.create_ephemeral_token(ndb.kbid, ttl=ttl)
        return f"{url}?eph-token={token.token}"

    @kb
    async def send_to_process(
        self, *, rid: Optional[str] = None, slug: Optional[str] = None, **kwargs
    ):
        ndb: AsyncNucliaDBClient = kwargs["ndb"]
        kw = {
            "kbid": ndb.kbid,
        }
        if rid:
            kw["rid"] = rid
            if slug:
                kw["slug"] = slug
            await ndb.ndb.reprocess_resource(**kw)
        elif slug:
            kw["rslug"] = slug
            await ndb.ndb.reprocess_resource_by_slug(**kw)
        else:
            raise ValueError("Either rid or slug must be provided")

    @kb
    async def update(
        self, *, rid: Optional[str] = None, slug: Optional[str] = None, **kwargs
    ):
        ndb: AsyncNucliaDBClient = kwargs["ndb"]
        kw = {
            "kbid": ndb.kbid,
        }
        for param in RESOURCE_ATTRIBUTES:
            if param in kwargs:
                kw[param] = kwargs.get(param)  # type: ignore
        if rid:
            kw["rid"] = rid
            if slug:
                kw["slug"] = slug
            await ndb.ndb.update_resource(**kw)
        elif slug:
            kw["rslug"] = slug
            await ndb.ndb.update_resource_by_slug(**kw)
        else:
            raise ValueError("Either rid or slug must be provided")

    @kb
    async def delete(
        self, *, rid: Optional[str] = None, slug: Optional[str] = None, **kwargs
    ):
        ndb: AsyncNucliaDBClient = kwargs["ndb"]
        if rid:
            await ndb.ndb.delete_resource(kbid=ndb.kbid, rid=rid)
        elif slug:
            await ndb.ndb.delete_resource_by_slug(kbid=ndb.kbid, rslug=slug)
        else:
            raise ValueError("Either rid or slug must be provided")
