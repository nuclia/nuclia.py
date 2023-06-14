from __future__ import annotations

from typing import Optional

from nucliadb_models import Origin
from nuclia.cli.auth import NucliaAuth
from nuclia.decorators import kb

from nuclia.lib.kb import NucliaDBClient
from nuclia.data import get_auth
import requests
import os
import mimetypes
from tqdm import tqdm


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
            mimetype = "/".join()
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

    @kb
    def remote(
        self,
        *,
        ndb: NucliaDBClient,
        url: str,
        rid: Optional[str] = None,
        field: Optional[str] = "file",
    ):
        """Option to upload a remote url to a Nuclia KnowledgeBox"""
        with requests.get(url, stream=True) as r:
            filename = url.split("/")[-1]
            size = int(r.headers.get("Content-Length"))
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
