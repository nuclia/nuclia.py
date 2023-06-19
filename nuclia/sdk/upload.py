from __future__ import annotations

import mimetypes
import os
from datetime import datetime
from typing import Optional
from uuid import uuid4

import requests
from tqdm import tqdm

from nuclia.data import get_auth
from nuclia.decorators import kb
from nuclia.lib.conversations import Conversations
from nuclia.lib.kb import NucliaDBClient
from nuclia.sdk.auth import NucliaAuth


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
    ):
        """Option to upload a file from filesystem to a Nuclia KnowledgeBox"""
        filename = path.split("/")[-1]
        size = os.path.getsize(path)
        mimetype_result = mimetypes.guess_type(path)
        if None in mimetype_result:
            mimetype = "application/octet-stream"
        else:
            mimetype = "/".join(mimetype_result)  # type: ignore
        with open(path, "rb") as upload_file:
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

    @kb
    def conversation(self, *, ndb: NucliaDBClient, path: str):
        """Option to upload a conversation from filesystem to a Nuclia KnowledgeBox"""
        conversations = Conversations.parse_file(path)
        if conversations.conversations is None:
            return

        for conversation in conversations.conversations:
            if conversation.messages is None:
                continue
            rid = conversation.slug if conversation.slug is not None else uuid4().hex
            ndb.ndb.create_resource(
                kbid=ndb.kbid,
                slug=rid,
                icon="application/conversation",
                conversations={
                    rid: {
                        "messages": [
                            {
                                "who": message.who
                                if message.who is not None
                                else uuid4().hex,
                                "to": [x for x in message.to]
                                if message.to is not None
                                else [],
                                "ident": message.uuid
                                if message.uuid is not None
                                else uuid4().hex,
                                "timestamp": message.timestamp
                                if message.timestamp is not None
                                else datetime.now().isoformat(),
                                "content": {
                                    "text": message.message.text,
                                    "format": message.message.format
                                    if message.message.format is not None
                                    else "PLAIN",
                                },
                            }
                            for message in conversation.messages
                        ]
                    }
                },
            )

    @kb
    def remote(
        self,
        *,
        ndb: NucliaDBClient,
        origin: str,
        rid: Optional[str] = None,
        field: Optional[str] = "file",
    ):
        """Option to upload a remote url to a Nuclia KnowledgeBox"""
        with requests.get(origin, stream=True) as r:
            filename = origin.split("/")[-1]
            size_str = r.headers.get("Content-Length")
            if size_str is None:
                size_str = "-1"
            size = int(size_str)
            upload_url = ndb.start_tus_upload(
                rid=rid,
                field=field,
                size=size,
                filename=filename,
                content_type=r.headers.get("Content-Type", "application/octet-stream"),
            )
            offset = 0
            for _ in tqdm(range((size // 524288) + 1)):
                chunk = r.raw.read(524288)
                offset = ndb.patch_tus_upload(upload_url, chunk, offset)
