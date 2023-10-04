import base64
from enum import Enum
from typing import Optional

import httpx
import requests
from nucliadb_models.search import ChatRequest
from nucliadb_sdk import NucliaDB, Region

from nuclia.lib.utils import handle_http_errors

RESOURCE_PATH = "/resource/{rid}"
RESOURCE_PATH_BY_SLUG = "/slug/{slug}"
SEARCH_PATH = "/search"
CREATE_RESOURCE_PATH = "/resources"
CREATE_VECTORSET = "/vectorset/{vectorset}"
VECTORSETS = "/vectorsets"
COUNTER = "/counters"
SEARCH_URL = "/search"
FIND_URL = "/find"
CHAT_URL = "/chat"
LABELS_URL = "/labelsets"
ENTITIES_URL = "/entitiesgroups"
DOWNLOAD_URL = "/{uri}"
TUS_UPLOAD_RESOURCE_URL = "/resource/{rid}/file/{field}/tusupload"
TUS_UPLOAD_URL = "/tusupload"


class Environment(str, Enum):
    CLOUD = "CLOUD"
    OSS = "OSS"


class NucliaDBClient:
    environment: Environment
    base_url: str
    api_key: Optional[str]
    url: Optional[str] = None
    reader_session: Optional[httpx.Client] = None
    stream_session: Optional[requests.Session] = None
    writer_session: Optional[httpx.Client] = None

    def __init__(
        self,
        *,
        environment: Environment = Environment.CLOUD,
        url: Optional[str] = None,
        api_key: Optional[str] = None,
        user_token: Optional[str] = None,
        region: Optional[str] = None,
        base_url: Optional[str] = None,
    ):
        if environment == Environment.OSS:
            region_obj = Region.ON_PREM
        else:
            region_obj = Region(region)

        headers = {}
        if user_token is not None:
            headers["Authorization"] = f"Bearer {user_token}"
        headers["X-SYNCHRONOUS"] = "True"
        if base_url is not None:
            v2url = base_url
        if base_url is None and url is not None:
            v2url = "/".join(url.split("/")[:-3])
        self.base_url = v2url
        self.ndb = NucliaDB(
            region=region_obj, url=v2url, api_key=api_key, headers=headers
        )
        self.api_key = api_key
        self.environment = environment

        if url is not None:
            self.kbid = url.strip("/").split("/")[-1]
            self.url = url

        if environment == Environment.CLOUD and api_key is not None:
            reader_headers = {
                "X-NUCLIA-SERVICEACCOUNT": f"Bearer {api_key}",
            }
            writer_headers = {
                "X-NUCLIA-SERVICEACCOUNT": f"Bearer {api_key}",
                "X-SYNCHRONOUS": "True",
            }
        elif (
            environment == Environment.CLOUD
            and api_key is None
            and user_token is not None
        ):
            reader_headers = {
                "Authorization": f"Bearer {user_token}",
            }
            writer_headers = {
                "Authorization": f"Bearer {user_token}",
                "X-SYNCHRONOUS": "True",
            }
        elif (
            environment == Environment.CLOUD and api_key is None and user_token is None
        ):
            # Public
            reader_headers = {}
            writer_headers = {}
        else:
            reader_headers = {
                "X-NUCLIADB-ROLES": f"READER",
            }
            writer_headers = {
                "X-NUCLIADB-ROLES": f"WRITER",
                "X-SYNCHRONOUS": "True",
            }

        if url is not None:
            self.reader_session = httpx.Client(
                headers=reader_headers, base_url=url  # type: ignore
            )
            self.stream_session = requests.Session()
            self.stream_session.headers.update(reader_headers)
            self.writer_session = httpx.Client(
                headers=writer_headers, base_url=url  # type: ignore
            )

    def chat(self, request: ChatRequest):
        if self.url is None or self.stream_session is None:
            raise Exception("KB not configured")
        url = f"{self.url}{CHAT_URL}"
        response: requests.Response = self.stream_session.post(
            url, data=request.json(), stream=True
        )
        handle_http_errors(response)
        return response

    def download(self, uri: str) -> bytes:
        # uri has format
        # /kb/2a00d5b4-cfcc-48eb-85ac-d70bfd38b26d/resource/41d02aac4ade48098b23e38141807738/file/file/download/field
        # we need to remove the kb url
        if self.reader_session is None:
            raise Exception("KB not configured")

        uri_parts = uri.split("/")
        if len(uri_parts) < 9:
            raise AttributeError("Not a valid download uri")

        new_uri = "/".join(uri_parts[3:])
        url = DOWNLOAD_URL.format(uri=new_uri)
        response: httpx.Response = self.reader_session.get(url)
        handle_http_errors(response)
        return response.content

    def start_tus_upload(
        self,
        size: int,
        filename: str,
        field: Optional[str] = None,
        rid: Optional[str] = None,
        md5: Optional[str] = None,
        content_type: str = "application/octet-stream",
    ):
        if self.writer_session is None:
            raise Exception("KB not configured")

        if rid is not None:
            if field is None:
                field = filename
            url = TUS_UPLOAD_RESOURCE_URL.format(rid=rid, field=field)
        else:
            url = TUS_UPLOAD_URL
        encoded_filename = base64.b64encode(filename.encode()).decode()
        headers = {
            "upload-length": str(size),
            "tus-resumable": "1.0.0",
            "upload-metadata": f"filename {encoded_filename}",
            "content-type": content_type,
        }
        if md5 is not None:
            headers[
                "upload-metadata"
            ] += f",md5 {base64.b64encode(md5.encode()).decode()}"

        response: httpx.Response = self.writer_session.post(url, headers=headers)
        handle_http_errors(response)
        return response.headers.get("Location")

    def patch_tus_upload(self, upload_url: str, data: bytes, offset: int) -> int:
        if self.writer_session is None:
            raise Exception("KB not configured")

        headers = {
            "upload-offset": str(offset),
        }
        # upload url has all path, we should remove /kb/kbid/
        upload_url = "/" + "/".join(upload_url.split("/")[3:])
        response: httpx.Response = self.writer_session.patch(
            upload_url, headers=headers, content=data
        )
        handle_http_errors(response)
        return int(response.headers.get("Upload-Offset"))
