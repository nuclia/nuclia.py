from __future__ import annotations

import hashlib
import mimetypes
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional, Tuple
from uuid import uuid4

import aiofiles
import backoff
import requests
from nucliadb_models.text import TextFormat
from nucliadb_sdk import exceptions
from tqdm import tqdm

from nuclia.data import get_async_auth, get_auth
from nuclia.decorators import kb
from nuclia.exceptions import DuplicateError, GettingRemoteFileError, RateLimitError
from nuclia.lib.conversations import Conversation
from nuclia.lib.kb import AsyncNucliaDBClient, NucliaDBClient
from nuclia.sdk.auth import AsyncNucliaAuth, NucliaAuth
from nuclia.sdk.logger import logger
from nuclia.sdk.resource import RESOURCE_ATTRIBUTES, AsyncNucliaResource, NucliaResource
from nuclia.lib.utils import build_httpx_async_client

MB = 1024 * 1024
CHUNK_SIZE = 5 * MB


class NucliaUpload:
    """
    Create or update resource content in a Nuclia KnowledgeBox.

    All commands accept the following parameters:
    - `rid`: Resource ID. If not provided, a new resource will be created.
    - `slug`: Resource slug. If it corresponds to an existing resource, the resource will be updated.
        If not provided, a unique value will be generated.
    - `field`: Field id. If not provided, a unique value will be generated.
    - `title`: resource title.
    - `usermetadata`: User metadata.
        See https://docs.nuclia.dev/docs/api#tag/Resources/operation/Create_Resource_kb__kbid__resources_post
    - `fieldmetadata`: Field metadata.
        See https://docs.nuclia.dev/docs/api#tag/Resources/operation/Create_Resource_kb__kbid__resources_post
    - `origin`: Origin metadata.
        See https://docs.nuclia.dev/docs/api#tag/Resources/operation/Create_Resource_kb__kbid__resources_post
    - `extra`: user-defined metadata.
    """

    @property
    def _auth(self) -> NucliaAuth:
        auth = get_auth()
        return auth

    @kb
    def file(
        self,
        *,
        path: str,
        rid: Optional[str] = None,
        field: Optional[str] = None,
        interpretTables: Optional[bool] = False,
        blanklineSplitter: Optional[bool] = False,
        mimetype: Optional[str] = None,
        extract_strategy: Optional[str] = None,
        **kwargs,
    ) -> Optional[str]:
        """Upload a file from filesystem to a Nuclia KnowledgeBox"""
        ndb: NucliaDBClient = kwargs["ndb"]
        filename = path.split(os.sep)[-1]
        size = os.path.getsize(path)
        mimetype = mimetype or mimetypes.guess_type(path)[0]
        if not mimetype:
            mimetype = "application/octet-stream"
        if interpretTables:
            mimetype += "+aitable"
        if blanklineSplitter:
            mimetype += "+blankline"
        is_new_resource = False
        if rid is not None:
            rid, is_new_resource = self._get_or_create_resource(
                rid=rid, icon=mimetype, **kwargs
            )
        if not field:
            field = uuid4().hex
        md5_hash = hashlib.md5()

        with open(path, "rb") as upload_file:
            md5_hash.update(upload_file.read())

        with open(path, "rb") as upload_file:
            try:
                upload_url = ndb.start_tus_upload(
                    rid=rid,
                    field=field,
                    size=size,
                    filename=filename,
                    content_type=mimetype,
                    md5=md5_hash.hexdigest(),
                    extract_strategy=extract_strategy,
                )

                offset = 0
                for _ in tqdm(range((size // CHUNK_SIZE) + 1)):
                    chunk = upload_file.read(CHUNK_SIZE)
                    offset = ndb.patch_tus_upload(
                        upload_url=upload_url, data=chunk, offset=offset
                    )
            except DuplicateError:
                logger.info("Duplicated file")
            except Exception:
                logger.exception("Error on uploading")
                if is_new_resource:
                    ndb.ndb.delete_resource(kbid=ndb.kbid, rid=rid)
                raise
        return rid

    @kb
    def conversation(self, *, path: str, **kwargs) -> str:
        """Upload a conversation from a JSON located on the filesystem to a Nuclia KnowledgeBox"""
        with open(path, "rb") as f:
            json_data = f.read()
            conversation = Conversation.model_validate_json(json_data).root
        if conversation is None or len(conversation) == 0:
            return ""

        field = kwargs.get("field") or uuid4().hex
        conversations = {
            field: {
                "messages": [
                    {
                        "who": message.who if message.who is not None else uuid4().hex,
                        "to": [x for x in message.to] if message.to is not None else [],
                        "ident": (
                            message.ident if message.ident is not None else uuid4().hex
                        ),
                        "timestamp": (
                            message.timestamp
                            if message.timestamp is not None
                            else datetime.now().isoformat()
                        ),
                        "content": {
                            "text": message.content.text,
                            "format": (
                                message.content.format
                                if message.content.format is not None
                                else "PLAIN"
                            ),
                        },
                    }
                    for message in conversation
                ]
            }
        }

        rid, is_new_resource = self._get_or_create_resource(
            conversations=conversations,
            **kwargs,
        )
        if not is_new_resource:
            self._update_resource(
                rid=rid,
                conversations=conversations,
                **kwargs,
            )
        return rid

    @kb
    def text(
        self,
        *,
        format: TextFormat = TextFormat.PLAIN,
        path: Optional[str] = None,
        stdin: Optional[bool] = False,
        **kwargs,
    ) -> str:
        """Upload a text from filesystem or from standard input to a Nuclia KnowledgeBox.

        Format can be one of: PLAIN, HTML, MARKDOWN, RST"""
        if path is None and not stdin:
            raise ValueError("Either path or stdin must be provided")
        if path:
            text = Path(path).resolve().open().read()
        else:
            text = sys.stdin.read()
        icon = "text/plain"
        if format == "HTML":
            icon = "text/html"
        elif format == "MARKDOWN":
            icon = "text/markdown"
        elif format == "RST":
            icon = "text/x-rst"
        field = kwargs.get("field") or uuid4().hex
        texts = {
            field: {
                "body": text,
                "format": format,
            }
        }
        extract_strategy = kwargs.get("extract_strategy")
        if extract_strategy is not None:
            texts[field]["extract_strategy"] = extract_strategy
        rid, is_new_resource = self._get_or_create_resource(
            texts=texts,
            icon=icon,
            **kwargs,
        )
        if not is_new_resource:
            self._update_resource(
                rid=rid,
                texts=texts,
                **kwargs,
            )
        return rid

    @kb
    def link(
        self,
        *,
        uri: str,
        css_selector: Optional[str] = None,
        **kwargs,
    ) -> str:
        """Upload an URL to a Nuclia KnowledgeBox."""
        field = kwargs.get("field") or uuid4().hex
        links = {
            field: {
                "uri": uri,
                "css_selector": css_selector,
            }
        }
        extract_strategy = kwargs.get("extract_strategy")
        if extract_strategy is not None:
            links[field]["extract_strategy"] = extract_strategy
        kwargs["icon"] = "application/stf-link"
        rid, is_new_resource = self._get_or_create_resource(
            links=links,
            **kwargs,
        )
        if not is_new_resource:
            self._update_resource(
                rid=rid,
                links=links,
                **kwargs,
            )
        return rid

    @kb
    def remote(
        self,
        *,
        origin: str,
        rid: Optional[str] = None,
        field: Optional[str] = "file",
        interpretTables: Optional[bool] = False,
        blanklineSplitter: Optional[bool] = False,
        extract_strategy: Optional[str] = None,
        **kwargs,
    ) -> str:
        """Upload a remote url to a Nuclia KnowledgeBox"""
        ndb = kwargs["ndb"]
        with requests.get(origin, stream=True, allow_redirects=True) as r:
            try:
                r.raise_for_status()
            except Exception as ex:
                raise GettingRemoteFileError(
                    f"Unable to get remote file {origin}: {ex}"
                ) from ex
            filename = origin.split(os.sep)[-1]
            size_str = r.headers.get("Content-Length")
            if size_str is None:
                size_str = "-1"
            size = int(size_str)
            mimetype = r.headers.get("Content-Type", "application/octet-stream")
            if interpretTables:
                mimetype += "+aitable"
            if blanklineSplitter:
                mimetype += "+blankline"
            rid, is_new_resource = self._get_or_create_resource(
                rid=rid, icon=mimetype, **kwargs
            )
            try:
                upload_url = ndb.start_tus_upload(
                    rid=rid,
                    field=field,
                    size=size,
                    filename=filename,
                    content_type=mimetype,
                    extract_strategy=extract_strategy,
                )
                offset = 0
                for _ in tqdm(range((size // CHUNK_SIZE) + 1)):
                    chunk = r.raw.read(CHUNK_SIZE)
                    offset = ndb.patch_tus_upload(upload_url, chunk, offset)
            except Exception:
                logger.exception("Error uploading")
                if is_new_resource:
                    ndb.ndb.delete_resource(kbid=ndb.kbid, rid=rid)
                raise
        return rid

    @backoff.on_exception(
        backoff.expo,
        RateLimitError,
        jitter=backoff.random_jitter,
        max_tries=5,
        factor=10,
    )
    def _get_or_create_resource(*args, **kwargs) -> Tuple[str, bool]:
        rid = kwargs.get("rid")
        if rid:
            return (rid, False)
        ndb = kwargs["ndb"]
        slug = kwargs.get("slug")
        need_to_create_resource = slug is None
        if slug:
            try:
                resource = ndb.ndb.get_resource_by_slug(kbid=ndb.kbid, slug=slug)
                rid = resource.id
                logger.warning(f"Using existing resource: {rid}")
                need_to_create_resource = False
            except exceptions.NotFoundError:
                need_to_create_resource = True
        else:
            slug = uuid4().hex

        if need_to_create_resource:
            kw = {
                "kbid": ndb.kbid,
                "slug": slug,
            }
            for param in RESOURCE_ATTRIBUTES:
                if param in kwargs:
                    kw[param] = kwargs.get(param)
            resource = ndb.ndb.create_resource(**kw)
            rid = resource.uuid
            logger.warning(f"New resource created: {rid}")

        return (rid, need_to_create_resource)

    @backoff.on_exception(
        backoff.expo,
        RateLimitError,
        jitter=backoff.random_jitter,
        max_tries=5,
        factor=10,
    )
    def _update_resource(self, rid: str, **kwargs):
        return NucliaResource().update(rid=rid, **kwargs)


class AsyncNucliaUpload:
    """
    Create or update resource content in a Nuclia KnowledgeBox.

    All commands accept the following parameters:
    - `rid`: Resource ID. If not provided, a new resource will be created.
    - `slug`: Resource slug. If it corresponds to an existing resource, the resource will be updated.
        If not provided, a unique value will be generated.
    - `field`: Field id. If not provided, a unique value will be generated.
    - `title`: resource title.
    - `usermetadata`: User metadata.
        See https://docs.nuclia.dev/docs/api#tag/Resources/operation/Create_Resource_kb__kbid__resources_post
    - `fieldmetadata`: Field metadata.
        See https://docs.nuclia.dev/docs/api#tag/Resources/operation/Create_Resource_kb__kbid__resources_post
    - `origin`: Origin metadata.
        See https://docs.nuclia.dev/docs/api#tag/Resources/operation/Create_Resource_kb__kbid__resources_post
    - `extra`: user-defined metadata.
    """

    @property
    def _auth(self) -> AsyncNucliaAuth:
        auth = get_async_auth()
        return auth

    @kb
    async def file(
        self,
        *,
        path: str,
        rid: Optional[str] = None,
        field: Optional[str] = None,
        mimetype: Optional[str] = None,
        interpretTables: Optional[bool] = False,
        blanklineSplitter: Optional[bool] = False,
        extract_strategy: Optional[str] = None,
        **kwargs,
    ) -> str:
        """Upload a file from filesystem to a Nuclia KnowledgeBox"""
        ndb: AsyncNucliaDBClient = kwargs["ndb"]
        filename = path.split(os.sep)[-1]
        size = os.path.getsize(path)
        mimetype = mimetype or mimetypes.guess_type(path)[0]
        if not mimetype:
            mimetype = "application/octet-stream"
        if interpretTables:
            mimetype += "+aitable"
        if blanklineSplitter:
            mimetype += "+blankline"
        rid, is_new_resource = await self._get_or_create_resource(
            rid=rid, icon=mimetype, **kwargs
        )
        if not field:
            field = uuid4().hex
        md5_hash = hashlib.md5()

        async with aiofiles.open(path, "rb") as upload_file:
            md5_hash.update(await upload_file.read())

        async with aiofiles.open(path, "rb") as upload_file:
            try:
                upload_url = await ndb.start_tus_upload(
                    rid=rid,
                    field=field,
                    size=size,
                    filename=filename,
                    content_type=mimetype,
                    md5=md5_hash.hexdigest(),
                    extract_strategy=extract_strategy,
                )
                offset = 0
                for _ in tqdm(range((size // CHUNK_SIZE) + 1)):
                    chunk = await upload_file.read(CHUNK_SIZE)
                    offset = await ndb.patch_tus_upload(
                        upload_url=upload_url, data=chunk, offset=offset
                    )
            except Exception:
                logger.exception("Error on uploading")
                if is_new_resource:
                    await ndb.ndb.delete_resource(kbid=ndb.kbid, rid=rid)
                raise
        return rid

    @kb
    async def conversation(self, *, path: str, **kwargs) -> str:
        """Upload a conversation from a JSON located on the filesystem to a Nuclia KnowledgeBox"""
        with open(path, "rb") as f:
            json_data = f.read()
        conversation = Conversation.model_validate_json(json_data).root
        if conversation is None or len(conversation) == 0:
            return ""

        field = kwargs.get("field") or uuid4().hex
        conversations = {
            field: {
                "messages": [
                    {
                        "who": message.who if message.who is not None else uuid4().hex,
                        "to": [x for x in message.to] if message.to is not None else [],
                        "ident": (
                            message.ident if message.ident is not None else uuid4().hex
                        ),
                        "timestamp": (
                            message.timestamp
                            if message.timestamp is not None
                            else datetime.now().isoformat()
                        ),
                        "content": {
                            "text": message.content.text,
                            "format": (
                                message.content.format
                                if message.content.format is not None
                                else "PLAIN"
                            ),
                        },
                    }
                    for message in conversation
                ]
            }
        }

        rid, is_new_resource = await self._get_or_create_resource(
            conversations=conversations,
            **kwargs,
        )
        if not is_new_resource:
            await self._update_resource(
                rid=rid,
                conversations=conversations,
                **kwargs,
            )
        return rid

    @kb
    async def text(
        self,
        *,
        format: TextFormat = TextFormat.PLAIN,
        path: Optional[str] = None,
        stdin: Optional[bool] = False,
        **kwargs,
    ) -> str:
        """Upload a text from filesystem or from standard input to a Nuclia KnowledgeBox.

        Format can be one of: PLAIN, HTML, MARKDOWN, RST"""
        if path is None and not stdin:
            raise ValueError("Either path or stdin must be provided")
        if path:
            text = Path(path).resolve().open().read()
        else:
            text = sys.stdin.read()
        icon = "text/plain"
        if format == "HTML":
            icon = "text/html"
        elif format == "MARKDOWN":
            icon = "text/markdown"
        elif format == "RST":
            icon = "text/x-rst"
        field = kwargs.get("field") or uuid4().hex
        texts = {
            field: {
                "body": text,
                "format": format,
            }
        }
        extract_strategy = kwargs.get("extract_strategy")
        if extract_strategy is not None:
            texts[field]["extract_strategy"] = extract_strategy
        rid, is_new_resource = await self._get_or_create_resource(
            texts=texts,
            icon=icon,
            **kwargs,
        )
        if not is_new_resource:
            await self._update_resource(
                rid=rid,
                texts=texts,
                **kwargs,
            )
        return rid

    @kb
    async def link(
        self,
        *,
        uri: str,
        **kwargs,
    ) -> str:
        """Upload an URL to a Nuclia KnowledgeBox."""
        field = kwargs.get("field") or uuid4().hex
        links = {
            field: {
                "uri": uri,
            }
        }
        extract_strategy = kwargs.get("extract_strategy")
        if extract_strategy is not None:
            links[field]["extract_strategy"] = extract_strategy
        kwargs["icon"] = "application/stf-link"
        rid, is_new_resource = await self._get_or_create_resource(
            links=links,
            **kwargs,
        )
        if not is_new_resource:
            await self._update_resource(
                rid=rid,
                links=links,
                **kwargs,
            )
        return rid

    @kb
    async def remote(
        self,
        *,
        origin: str,
        rid: Optional[str] = None,
        field: Optional[str] = "file",
        interpretTables: Optional[bool] = False,
        blanklineSplitter: Optional[bool] = False,
        extract_strategy: Optional[str] = None,
        **kwargs,
    ) -> str:
        """Upload a remote url to a Nuclia KnowledgeBox"""
        ndb: AsyncNucliaDBClient = kwargs["ndb"]
        client = build_httpx_async_client()
        async with client.stream("GET", origin, follow_redirects=True) as r:
            filename = origin.split(os.sep)[-1]
            size_str = r.headers.get("Content-Length")
            if size_str is None:
                size_str = "-1"
            size = int(size_str)
            mimetype = r.headers.get("Content-Type", "application/octet-stream")
            if interpretTables:
                mimetype += "+aitable"
            if blanklineSplitter:
                mimetype += "+blankline"
            rid, is_new_resource = await self._get_or_create_resource(
                rid=rid, icon=mimetype, **kwargs
            )
            try:
                upload_url = await ndb.start_tus_upload(
                    rid=rid,
                    field=field,
                    size=size,
                    filename=filename,
                    content_type=mimetype,
                    extract_strategy=extract_strategy,
                )
                offset = 0
                with tqdm(total=(size // CHUNK_SIZE) + 1) as p_bar:
                    async for chunk in r.aiter_raw(CHUNK_SIZE):
                        offset = await ndb.patch_tus_upload(upload_url, chunk, offset)
                        p_bar.update(1)

            except Exception:
                logger.exception("Error on uploading")
                if is_new_resource:
                    await ndb.ndb.delete_resource(kbid=ndb.kbid, rid=rid)
                raise
        return rid

    async def _get_or_create_resource(*args, **kwargs) -> Tuple[str, bool]:
        rid = kwargs.get("rid")
        if rid:
            return (rid, False)
        ndb: AsyncNucliaDBClient = kwargs["ndb"]
        slug = kwargs.get("slug")
        need_to_create_resource = slug is None
        if slug:
            try:
                resource = await ndb.ndb.get_resource_by_slug(kbid=ndb.kbid, slug=slug)
                rid = resource.id
                logger.warning(f"Using existing resource: {rid}")
                need_to_create_resource = False
            except exceptions.NotFoundError:
                need_to_create_resource = True
        else:
            slug = uuid4().hex

        if need_to_create_resource:
            kw = {
                "kbid": ndb.kbid,
                "slug": slug,
            }
            for param in RESOURCE_ATTRIBUTES:
                if param in kwargs:
                    kw[param] = kwargs.get(param)
            resource = await ndb.ndb.create_resource(**kw)
            rid = resource.uuid
            logger.warning(f"New resource created: {rid}")

        return (rid, need_to_create_resource)

    async def _update_resource(self, rid: str, **kwargs):
        return await AsyncNucliaResource().update(rid=rid, **kwargs)
