import base64
import csv
import os
from enum import Enum
from typing import Dict, Optional

import aiofiles
import httpx
import requests
from nucliadb_models.search import ChatRequest
from nucliadb_sdk import NucliaDB, NucliaDBAsync, Region
from tqdm import tqdm

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
DOWNLOAD_EXPORT_URL = "/export/{export_id}"
DOWNLOAD_URL = "/{uri}"
TUS_UPLOAD_RESOURCE_URL = "/resource/{rid}/file/{field}/tusupload"
TUS_UPLOAD_URL = "/tusupload"
ACTIVITY_LOG_URL = "/activity/download?type={type}&month={month}"
FEEDBACK_LOG_URL = "/feedback/{month}"


class Environment(str, Enum):
    CLOUD = "CLOUD"
    OSS = "OSS"


class LogType(str, Enum):
    NEW = "NEW"
    PROCESSED = "PROCESSED"
    MODIFIED = "MODIFIED"
    CHAT = "CHAT"
    SEARCH = "SEARCH"
    FEEDBACK = "FEEDBACK"


class BaseNucliaDBClient:
    environment: Environment
    base_url: str
    api_key: Optional[str]
    url: Optional[str] = None
    region: Region
    headers: Dict[str, str]

    reader_headers: Dict[str, str]
    writer_headers: Dict[str, str]

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
            self.region = Region.ON_PREM
        else:
            self.region = Region(region)

        self.headers = {}
        if user_token is not None:
            self.headers["Authorization"] = f"Bearer {user_token}"
        self.headers["X-SYNCHRONOUS"] = "True"
        if base_url is not None:
            v2url = base_url
        if base_url is None and url is not None:
            v2url = "/".join(url.split("/")[:-3])
        self.base_url = v2url
        self.api_key = api_key
        self.environment = environment

        if url is not None:
            self.kbid = url.strip("/").split("/")[-1]
            self.url = url

        if environment == Environment.CLOUD and api_key is not None:
            self.reader_headers = {
                "X-NUCLIA-SERVICEACCOUNT": f"Bearer {api_key}",
            }
            self.writer_headers = {
                "X-NUCLIA-SERVICEACCOUNT": f"Bearer {api_key}",
                "X-SYNCHRONOUS": "True",
            }
        elif (
            environment == Environment.CLOUD
            and api_key is None
            and user_token is not None
        ):
            self.reader_headers = {
                "Authorization": f"Bearer {user_token}",
            }
            self.writer_headers = {
                "Authorization": f"Bearer {user_token}",
                "X-SYNCHRONOUS": "True",
            }
        elif (
            environment == Environment.CLOUD and api_key is None and user_token is None
        ):
            # Public
            self.reader_headers = {}
            self.writer_headers = {}
        else:
            self.reader_headers = {
                "X-NUCLIADB-ROLES": f"READER",
            }
            self.writer_headers = {
                "X-NUCLIADB-ROLES": f"WRITER",
                "X-SYNCHRONOUS": "True",
            }


class NucliaDBClient(BaseNucliaDBClient):
    reader_session: Optional[httpx.Client] = None
    stream_session: Optional[requests.Session] = None
    writer_session: Optional[httpx.Client] = None
    ndb: NucliaDB

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
        super().__init__(
            environment=environment,
            url=url,
            api_key=api_key,
            user_token=user_token,
            region=region,
            base_url=base_url,
        )
        self.ndb = NucliaDB(
            region=self.region, url=self.base_url, api_key=api_key, headers=self.headers
        )

        if url is not None:
            self.reader_session = httpx.Client(
                headers=self.reader_headers, base_url=url  # type: ignore
            )
            self.stream_session = requests.Session()
            self.stream_session.headers.update(self.reader_headers)
            self.writer_session = httpx.Client(
                headers=self.writer_headers, base_url=url  # type: ignore
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

    def logs(self, type: LogType, month: str) -> list[list[str]]:
        if self.reader_session is None:
            raise Exception("KB not configured")

        if type != "FEEDBACK":
            url = ACTIVITY_LOG_URL.format(type=type, month=month)
            response: httpx.Response = self.reader_session.get(url)
            handle_http_errors(response)
            return [row for row in csv.reader(response.iter_lines())]
        else:
            feedback_url = f"{self.url}{FEEDBACK_LOG_URL.format(month=month)}"
            feedback_response: httpx.Response = self.reader_session.get(feedback_url)
            handle_http_errors(feedback_response)
            feedbacks = [row for row in csv.reader(feedback_response.iter_lines())]
            answers = self.logs(type=LogType.CHAT, month=month)
            # first row with the columns headers
            results = [[*feedbacks[0], *answers[0][:-1]]]
            for feedback in feedbacks[1:]:
                learning_id = feedback[1]
                # search for the corresponding question/answer
                # (the learning id is the same for both question/answer and feedback,
                # and is the second column in the Q/A csv)
                matching_answers = [
                    answer for answer in answers if answer[1] == learning_id
                ]
                if len(matching_answers) > 0:
                    results.append([*feedback, *matching_answers[0][:-1]])
                else:
                    results.append(feedback)
            return results


class AsyncNucliaDBClient(BaseNucliaDBClient):
    reader_session: Optional[httpx.AsyncClient] = None
    writer_session: Optional[httpx.AsyncClient] = None
    ndb: NucliaDBAsync

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
        super().__init__(
            environment=environment,
            url=url,
            api_key=api_key,
            user_token=user_token,
            region=region,
            base_url=base_url,
        )

        self.ndb = NucliaDBAsync(
            region=self.region, url=self.base_url, api_key=api_key, headers=self.headers
        )

        if url is not None:
            self.reader_session = httpx.AsyncClient(
                headers=self.reader_headers, base_url=url  # type: ignore
            )
            self.writer_session = httpx.AsyncClient(
                headers=self.writer_headers, base_url=url  # type: ignore
            )

    async def chat(self, request: ChatRequest):
        if self.url is None or self.reader_session is None:
            raise Exception("KB not configured")
        url = f"{self.url}{CHAT_URL}"
        req = self.reader_session.build_request("POST", url, json=request.dict())
        response = await self.reader_session.send(req, stream=True)
        handle_http_errors(response)
        return response

    async def download_export(self, export_id: str, path: str, chunk_size: int):
        if self.reader_session is None:
            raise Exception("KB not configured")

        parent = "/".join(path.split("/")[:-1])
        if os.path.exists(parent) is False:
            os.makedirs(parent)

        status = await self.ndb.export_status(kbid=self.kbid, export_id=export_id)
        export_size = status.total

        url = DOWNLOAD_EXPORT_URL.format(export_id=export_id)
        async with self.reader_session.stream("GET", url) as content:
            async with aiofiles.open(path, "wb") as file:
                with tqdm(
                    desc=f"Downloading data",
                    total=export_size,
                    unit="iB",
                    unit_scale=True,
                ) as pbar:
                    async for chunk in content.aiter_bytes(chunk_size):
                        pbar.update(len(chunk))
                        await file.write(chunk)

    async def download(self, uri: str) -> bytes:
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
        response = await self.reader_session.get(url)
        handle_http_errors(response)
        return response.content

    async def start_tus_upload(
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

        response = await self.writer_session.post(url, headers=headers)
        handle_http_errors(response)
        return response.headers.get("Location")

    async def patch_tus_upload(self, upload_url: str, data: bytes, offset: int) -> int:
        if self.writer_session is None:
            raise Exception("KB not configured")

        headers = {
            "upload-offset": str(offset),
        }
        # upload url has all path, we should remove /kb/kbid/
        upload_url = "/" + "/".join(upload_url.split("/")[3:])
        response = await self.writer_session.patch(
            upload_url, headers=headers, content=data
        )
        handle_http_errors(response)
        return int(response.headers.get("Upload-Offset"))
