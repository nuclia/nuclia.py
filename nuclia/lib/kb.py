import base64
import csv
import os
from enum import Enum
from typing import Dict, Optional, Union

import aiofiles
import backoff
import httpx
import requests
from nucliadb_models.search import AskRequest, SummarizeRequest
from nuclia_models.common.utils import Aggregation
from nucliadb_sdk import NucliaDB, NucliaDBAsync, Region
from tqdm import tqdm
from nuclia_models.events.activity_logs import (  # type: ignore
    ActivityLogsQuery,
    ActivityLogsSearchQuery,
    ActivityLogsChatQuery,
    DownloadActivityLogsQuery,
    DownloadActivityLogsSearchQuery,
    DownloadActivityLogsChatQuery,
    EventType,
    DownloadFormat,
)
from nuclia_models.events.remi import RemiQuery
from nuclia_models.worker.tasks import TaskStartKB
from nuclia.exceptions import RateLimitError
from nuclia.lib.utils import handle_http_errors
from datetime import datetime

RESOURCE_PATH = "/resource/{rid}"
RESOURCE_PATH_BY_SLUG = "/slug/{slug}"
SEARCH_PATH = "/search"
CREATE_RESOURCE_PATH = "/resources"
CREATE_VECTORSET = "/vectorset/{vectorset}"
VECTORSETS = "/vectorsets"
COUNTER = "/counters"
SEARCH_URL = "/search"
FIND_URL = "/find"
ASK_URL = "/ask"
SUMMARIZE_URL = "/summarize"
LABELS_URL = "/labelsets"
ENTITIES_URL = "/entitiesgroups"
DOWNLOAD_EXPORT_URL = "/export/{export_id}"
DOWNLOAD_URL = "/{uri}"
TUS_UPLOAD_RESOURCE_URL = "/resource/{rid}/file/{field}/tusupload"
TUS_UPLOAD_URL = "/tusupload"
LEGACY_ACTIVITY_LOG_URL = "/activity/download?type={type}&month={month}"
ACTIVITY_LOG_URL = "/activity/{type}/query/download"
ACTIVITY_LOG_DOWNLOAD_REQUEST_URL = "/activity/download_request/{request_id}"
ACTIVITY_LOG_QUERY_URL = "/activity/{type}/query"
FEEDBACK_LOG_URL = "/feedback/{month}"
NOTIFICATIONS = "/notifications"
REMI_QUERY_URL = "/remi/query"
REMI_EVENT_URL = "/remi/events/{event_id}"
REMI_SCORES_URL = "/remi/scores"
LIST_TASKS = "/tasks"
START_TASK = "/task/start"
STOP_TASK = "/task/{task_id}/stop"
DELETE_TASK = "/task/{task_id}"
GET_TASK = "/task/{task_id}/inspect"
RESTART_TASK = "/task/{task_id}/restart"

DOWNLOAD_FORMAT_HEADERS = {
    DownloadFormat.CSV: "text/csv",
    DownloadFormat.NDJSON: "application/x-ndjson",
}


class Environment(str, Enum):
    CLOUD = "CLOUD"
    OSS = "OSS"


class LogType(str, Enum):
    # Nucliadb
    VISITED = "visited"
    MODIFIED = "modified"
    DELETED = "deleted"
    NEW = "new"
    SEARCH = "search"
    SUGGEST = "suggest"
    INDEXED = "indexed"
    CHAT = "chat"
    # Tasks
    STARTED = "started"
    STOPPED = "stopped"
    # Processor
    PROCESSED = "processed"


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
                "X-NUCLIADB-ROLES": "READER",
            }
            self.writer_headers = {
                "X-NUCLIADB-ROLES": "WRITER",
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
                headers=self.reader_headers,
                base_url=url,  # type: ignore
            )
            self.stream_session = requests.Session()
            self.stream_session.headers.update(self.reader_headers)
            self.writer_session = httpx.Client(
                headers=self.writer_headers,
                base_url=url,  # type: ignore
            )

    def __repr__(self):
        return f"{self.environment} - {self.url}"

    def notifications(self):
        if self.url is None or self.stream_session is None:
            raise Exception("KB not configured")
        url = f"{self.url}{NOTIFICATIONS}"
        response = self.stream_session.get(url, stream=True, timeout=3660)
        handle_http_errors(response)
        return response

    def ask(self, request: AskRequest, timeout: int = 1000):
        if self.url is None or self.stream_session is None:
            raise Exception("KB not configured")
        url = f"{self.url}{ASK_URL}"
        response: requests.Response = self.stream_session.post(
            url,
            data=request.model_dump_json(),
            stream=True,
            timeout=timeout,
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

    @backoff.on_exception(
        backoff.expo,
        RateLimitError,
        jitter=backoff.random_jitter,
        max_tries=5,
        factor=10,
    )
    def start_tus_upload(
        self,
        size: int,
        filename: str,
        field: Optional[str] = None,
        rid: Optional[str] = None,
        md5: Optional[str] = None,
        content_type: str = "application/octet-stream",
        extract_strategy: Optional[str] = None,
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
            headers["upload-metadata"] += (
                f",md5 {base64.b64encode(md5.encode()).decode()}"
            )
        if extract_strategy is not None:
            headers["x-extract-strategy"] = extract_strategy

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

        if type != "feedback":
            url = LEGACY_ACTIVITY_LOG_URL.format(type=type.value, month=month)
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

    def logs_query(
        self,
        type: EventType,
        query: Union[ActivityLogsQuery, ActivityLogsSearchQuery, ActivityLogsChatQuery],
    ) -> requests.Response:
        if self.stream_session is None:
            raise Exception("KB not configured")

        response = self.stream_session.post(
            f"{self.url}{ACTIVITY_LOG_QUERY_URL.format(type=type.value)}",
            json=query.model_dump(mode="json", exclude_unset=True),
            stream=True,
        )
        handle_http_errors(response)
        return response

    def logs_download(
        self,
        type: EventType,
        query: Union[
            DownloadActivityLogsQuery,
            DownloadActivityLogsSearchQuery,
            DownloadActivityLogsChatQuery,
        ],
        download_format: DownloadFormat,
    ):
        if self.reader_session is None:
            raise Exception("KB not configured")
        download_request_url = f"{self.url}{ACTIVITY_LOG_URL.format(type=type.value)}"
        format_header_value = DOWNLOAD_FORMAT_HEADERS.get(download_format)
        if format_header_value is None:
            raise ValueError()
        response: httpx.Response = self.reader_session.post(
            download_request_url,
            json=query.model_dump(mode="json", exclude_unset=True),
            headers={"accept": format_header_value},
        )
        handle_http_errors(response)
        return response

    def get_download_request(
        self,
        request_id: str,
    ):
        if self.reader_session is None:
            raise Exception("KB not configured")
        download_request_url = f"{self.url}{ACTIVITY_LOG_DOWNLOAD_REQUEST_URL.format(request_id=request_id)}"
        response: httpx.Response = self.reader_session.get(download_request_url)
        handle_http_errors(response)
        return response

    def remi_query(
        self,
        query: RemiQuery,
    ) -> httpx.Response:
        if self.reader_session is None:
            raise Exception("KB not configured")

        response: httpx.Response = self.reader_session.post(
            f"{self.url}{REMI_QUERY_URL}",
            json=query.model_dump(mode="json", exclude_unset=True),
            timeout=10,
        )
        handle_http_errors(response)
        return response

    def get_remi_event(
        self,
        event_id: int,
    ) -> httpx.Response:
        if self.reader_session is None:
            raise Exception("KB not configured")

        response: httpx.Response = self.reader_session.get(
            f"{self.url}{REMI_EVENT_URL.format(event_id=event_id)}"
        )
        handle_http_errors(response)
        return response

    def get_remi_scores(
        self,
        _from: datetime,
        to: Optional[datetime],
        aggregation: Aggregation,
    ) -> httpx.Response:
        if self.reader_session is None:
            raise Exception("KB not configured")
        params = {"from": _from.isoformat(), "aggregation": aggregation.value}
        if to:
            params["to"] = to.isoformat()
        response: httpx.Response = self.reader_session.get(
            f"{self.url}{REMI_SCORES_URL}", params=params, timeout=10
        )
        handle_http_errors(response)
        return response

    def list_tasks(self) -> httpx.Response:
        if self.reader_session is None:
            raise Exception("KB not configured")

        response: httpx.Response = self.reader_session.get(f"{self.url}{LIST_TASKS}")
        handle_http_errors(response)
        return response

    def start_task(self, body: TaskStartKB) -> httpx.Response:
        if self.writer_session is None:
            raise Exception("KB not configured")

        response: httpx.Response = self.writer_session.post(
            f"{self.url}{START_TASK}",
            json=body.model_dump(mode="json", exclude_unset=True),
        )
        handle_http_errors(response)
        return response

    def delete_task(self, task_id: str) -> httpx.Response:
        if self.writer_session is None:
            raise Exception("KB not configured")

        response: httpx.Response = self.writer_session.delete(
            f"{self.url}{DELETE_TASK.format(task_id=task_id)}",
        )
        handle_http_errors(response)
        return response

    def stop_task(self, task_id: str) -> httpx.Response:
        if self.writer_session is None:
            raise Exception("KB not configured")

        response: httpx.Response = self.writer_session.post(
            f"{self.url}{STOP_TASK.format(task_id=task_id)}",
        )
        handle_http_errors(response)
        return response

    def get_task(self, task_id: str) -> httpx.Response:
        if self.reader_session is None:
            raise Exception("KB not configured")

        response: httpx.Response = self.reader_session.get(
            f"{self.url}{GET_TASK.format(task_id=task_id)}",
        )
        handle_http_errors(response)
        return response

    def restart_task(self, task_id: str) -> httpx.Response:
        if self.writer_session is None:
            raise Exception("KB not configured")

        response: httpx.Response = self.writer_session.post(
            f"{self.url}{RESTART_TASK.format(task_id=task_id)}",
        )
        handle_http_errors(response)
        return response


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
                headers=self.reader_headers,
                base_url=url,  # type: ignore
            )
            self.writer_session = httpx.AsyncClient(
                headers=self.writer_headers,
                base_url=url,  # type: ignore
            )

    async def notifications(self):
        if self.url is None or self.reader_session is None:
            raise Exception("KB not configured")
        url = f"{self.url}{NOTIFICATIONS}"
        req = self.reader_session.build_request("GET", url, timeout=3660)
        response = await self.reader_session.send(req, stream=True)
        handle_http_errors(response)
        return response

    async def ask(self, request: AskRequest, timeout: int = 1000):
        if self.url is None or self.reader_session is None:
            raise Exception("KB not configured")
        url = f"{self.url}{ASK_URL}"
        req = self.reader_session.build_request(
            "POST", url, json=request.model_dump(), timeout=timeout
        )
        response = await self.reader_session.send(req, stream=True)
        handle_http_errors(response)
        return response

    async def download_export(self, export_id: str, path: str, chunk_size: int):
        if self.reader_session is None:
            raise Exception("KB not configured")

        parent = "/".join(path.split(os.sep)[:-1])
        if os.path.exists(parent) is False:
            os.makedirs(parent)

        status = await self.ndb.export_status(kbid=self.kbid, export_id=export_id)
        export_size = status.total

        url = DOWNLOAD_EXPORT_URL.format(export_id=export_id)
        async with self.reader_session.stream("GET", url) as content:
            async with aiofiles.open(path, "wb") as file:
                with tqdm(
                    desc="Downloading data",
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

    @backoff.on_exception(
        backoff.expo,
        RateLimitError,
        jitter=backoff.random_jitter,
        max_tries=5,
        factor=10,
    )
    async def start_tus_upload(
        self,
        size: int,
        filename: str,
        field: Optional[str] = None,
        rid: Optional[str] = None,
        md5: Optional[str] = None,
        content_type: str = "application/octet-stream",
        extract_strategy: Optional[str] = None,
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
            headers["upload-metadata"] += (
                f",md5 {base64.b64encode(md5.encode()).decode()}"
            )
        if extract_strategy is not None:
            headers["x-extract-strategy"] = extract_strategy

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

    async def summarize(self, request: SummarizeRequest, timeout: int = 1000):
        if self.url is None or self.writer_session is None:
            raise Exception("KB not configured")
        url = f"{self.url}{SUMMARIZE_URL}"
        assert self.reader_session
        response = await self.reader_session.post(
            url, json=request.model_dump(), timeout=timeout
        )
        handle_http_errors(response)
        return response
