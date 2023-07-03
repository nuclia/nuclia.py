from __future__ import annotations

import mimetypes
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional, Tuple
from uuid import uuid4

import requests
from nucliadb_models.text import TextFormat
from tqdm import tqdm

from nuclia.data import get_auth
from nuclia.decorators import kb
from nuclia.lib.conversations import Conversation
from nuclia.lib.kb import NucliaDBClient
from nuclia.sdk.auth import NucliaAuth
from nucliadb_sdk import exceptions


class NucliaUpload:
    @property
    def _auth(self) -> NucliaAuth:
        auth = get_auth()
        return auth

    @kb
    def file(
        self,
        *,
        ndb: NucliaDBClient,
        path: str,
        rid: Optional[str] = None,
        field: Optional[str] = None,
        **kwargs,
    ):
        """Option to upload a file from filesystem to a Nuclia KnowledgeBox"""
        filename = path.split("/")[-1]
        size = os.path.getsize(path)
        mimetype_result = mimetypes.guess_type(path)
        if None in mimetype_result:
            mimetype = "application/octet-stream"
        else:
            mimetype = "/".join(mimetype_result)  # type: ignore
        rid, is_new_resource = self._get_or_create_resource(ndb=ndb, rid=rid, icon=mimetype, **kwargs)
        
        with open(path, "rb") as upload_file:
            try:
                upload_url = ndb.start_tus_upload(
                    rid=rid,
                    field=field,
                    size=size,
                    filename=filename,
                    content_type=mimetype,
                )

                offset = 0
                for _ in tqdm(range((size // 524288) + 1)):
                    chunk = upload_file.read(524288)
                    offset = ndb.patch_tus_upload(
                        upload_url=upload_url, data=chunk, offset=offset
                    )
            except Exception as e:
                print(e)
                if is_new_resource:
                    ndb.ndb.delete_resource(kbid=ndb.kbid, rid=rid)
                sys.exit(1)

    @kb
    def conversation(self, *, ndb: NucliaDBClient, path: str, **kwargs):
        """Option to upload a conversation from filesystem to a Nuclia KnowledgeBox"""
        conversation = Conversation.parse_file(path).__root__
        if conversation is None or len(conversation) == 0:
            return

        field = kwargs.get("field") or uuid4().hex
        conversations={
                field: {
                    "messages": [
                        {
                            "who": message.who
                            if message.who is not None
                            else uuid4().hex,
                            "to": [x for x in message.to]
                            if message.to is not None
                            else [],
                            "ident": message.ident
                            if message.ident is not None
                            else uuid4().hex,
                            "timestamp": message.timestamp
                            if message.timestamp is not None
                            else datetime.now().isoformat(),
                            "content": {
                                "text": message.content.text,
                                "format": message.content.format
                                if message.content.format is not None
                                else "PLAIN",
                            },
                        }
                        for message in conversation
                    ]
                }
            }

        rid, is_new_resource = self._get_or_create_resource(
            ndb=ndb,
            conversations=conversations,
            **kwargs,
        )
        if not is_new_resource:
            ndb.ndb.update_resource(
                kbid=ndb.kbid,
                rid=rid,
                conversations=conversations,
                origin=kwargs.get("origin"),
                extra=kwargs.get("extra"),
            )

    @kb
    def text(
        self,
        *,
        ndb: NucliaDBClient,
        format: TextFormat = TextFormat.PLAIN,
        path: Optional[str] = None,
        stdin: Optional[bool] = False,
        **kwargs,
    ):
        """Option to upload a text from filesystem to a Nuclia KnowledgeBox"""
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
        texts={
            field: {
                "body": text,
                "format": format,
            }
        }
        rid, is_new_resource = self._get_or_create_resource(
            ndb=ndb,
            texts=texts,
            icon=icon,
            **kwargs,
        )
        if not is_new_resource:
            ndb.ndb.update_resource(
                kbid=ndb.kbid,
                rid=rid,
                texts=texts,
                origin=kwargs.get("origin"),
                extra=kwargs.get("extra"),
            )

    @kb
    def remote(
        self,
        *,
        ndb: NucliaDBClient,
        origin: str,
        rid: Optional[str] = None,
        field: Optional[str] = "file",
        **kwargs,
    ):
        """Option to upload a remote url to a Nuclia KnowledgeBox"""
        with requests.get(origin, stream=True) as r:
            filename = origin.split("/")[-1]
            size_str = r.headers.get("Content-Length")
            if size_str is None:
                size_str = "-1"
            size = int(size_str)
            mimetype = r.headers.get("Content-Type", "application/octet-stream")
            rid, is_new_resource = self._get_or_create_resource(ndb=ndb, rid=rid, icon=mimetype, **kwargs)
            try:
                upload_url = ndb.start_tus_upload(
                    rid=rid,
                    field=field,
                    size=size,
                    filename=filename,
                    content_type=mimetype,
                )
                offset = 0
                for _ in tqdm(range((size // 524288) + 1)):
                    chunk = r.raw.read(524288)
                    offset = ndb.patch_tus_upload(upload_url, chunk, offset)
            except Exception as e:
                print(e)
                if is_new_resource:
                    ndb.ndb.delete_resource(kbid=ndb.kbid, rid=rid)
                sys.exit(1)

    def _get_or_create_resource(*args, **kwargs) -> Tuple[str, bool]:
        rid = kwargs.get("rid")
        if rid:
            return rid
        ndb = kwargs["ndb"]
        slug = kwargs.get("slug")
        need_to_create_resource = slug is None
        if slug:
            try:
                resource = ndb.ndb.get_resource_by_slug(kbid=ndb.kbid, slug=slug)
                rid = resource.id
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
            for param in ["icon", "origin", "extra", "conversations", "texts"]:
                if kwargs.get(param):
                    kw[param] = kwargs.get(param)
            resource = ndb.ndb.create_resource(**kw)
            rid = resource.uuid

        return (rid, need_to_create_resource)
