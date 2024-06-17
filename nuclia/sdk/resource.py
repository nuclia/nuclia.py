from typing import List, Optional
from uuid import uuid4

from nucliadb_models.metadata import ResourceProcessingStatus
from nucliadb_models.resource import Resource

from nuclia import get_list_parameter
from nuclia.decorators import kb, pretty
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
