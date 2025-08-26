import asyncio
from time import monotonic, sleep
from typing import Union

from nuclia_models.events.activity_logs import (  # type: ignore
    ActivityLogsAskQuery,
    ActivityLogsQuery,
    ActivityLogsSearchQuery,
    DownloadActivityLogsAskQuery,
    DownloadActivityLogsQuery,
    DownloadActivityLogsSearchQuery,
    DownloadFormat,
    EventType,
)

from nuclia.decorators import kb
from nuclia.lib.kb import AsyncNucliaDBClient, NucliaDBClient
from nuclia.lib.models import (
    ActivityLogsOutput,
    ActivityLogsQueryResponse,
    DownloadRequestOutput,
)
from nuclia.sdk.logger import logger

WAIT_FOR_DOWNLOAD_TIMEOUT = 120


class NucliaLogs:
    @kb
    def query(
        self,
        *args,
        type: Union[EventType, str],
        query: Union[
            dict,
            ActivityLogsQuery,
            ActivityLogsSearchQuery,
            ActivityLogsAskQuery,
        ],
        **kwargs,
    ) -> ActivityLogsOutput:
        """
        Query activity logs.

        :param type: VISITED, MODIFIED, DELETED, NEW, SEARCH, SUGGEST, INDEXED, CHAT, ASK, STARTED, STOPPED, PROCESSED
        :param query: ActivityLogsQuery
        """
        _type = EventType[type.upper()] if isinstance(type, str) else type
        _query: Union[
            ActivityLogsQuery,
            ActivityLogsSearchQuery,
            ActivityLogsAskQuery,
        ]
        if isinstance(query, dict):
            if _type in (EventType.ASK, EventType.CHAT):  # TODO: deprecate chat event
                _query = ActivityLogsAskQuery.model_validate(query)
            elif type is EventType.SEARCH:
                _query = ActivityLogsSearchQuery.model_validate(query)
            else:
                _query = ActivityLogsQuery.model_validate(query)
        else:
            _query = query

        ndb: NucliaDBClient = kwargs["ndb"]
        response = ndb.logs_query(type=_type, query=_query)
        output: list[ActivityLogsQueryResponse] = []  # type: ignore
        for line in response.iter_lines():
            output.append(ActivityLogsQueryResponse.model_validate_json(line))
        return ActivityLogsOutput(
            data=output, has_more=response.headers["has-more"].lower() == "true"
        )

    @kb
    def download(
        self,
        *args,
        type: Union[EventType, str],
        query: Union[
            dict,
            DownloadActivityLogsQuery,
            DownloadActivityLogsSearchQuery,
            DownloadActivityLogsAskQuery,
        ],
        download_format: Union[DownloadFormat, str],
        wait: bool = False,
        **kwargs,
    ) -> DownloadRequestOutput:  # type: ignore
        """
        Download activity logs.

        :param type: VISITED, MODIFIED, DELETED, NEW, SEARCH, SUGGEST, INDEXED, CHAT, ASK, STARTED, STOPPED, PROCESSED
        :param download_format: NDJSON, CSV
        :param query: DownloadActivityLogsQuery
        """
        _type = EventType[type.upper()] if isinstance(type, str) else type
        _format = (
            DownloadFormat[download_format.upper()]
            if isinstance(download_format, str)
            else download_format
        )

        _query: Union[
            dict,
            DownloadActivityLogsQuery,
            DownloadActivityLogsSearchQuery,
            DownloadActivityLogsAskQuery,
        ]
        if isinstance(query, dict):
            if _type in (EventType.ASK, EventType.CHAT):  # TODO: deprecate chat event
                _query = DownloadActivityLogsAskQuery.model_validate(query)
            elif type is EventType.SEARCH:
                _query = DownloadActivityLogsSearchQuery.model_validate(query)
            else:
                _query = DownloadActivityLogsQuery.model_validate(query)
        else:
            _query = query

        ndb: NucliaDBClient = kwargs["ndb"]
        response = ndb.logs_download(type=_type, query=_query, download_format=_format)

        download_request = DownloadRequestOutput.model_validate(response.json())  # type: ignore

        if not wait:
            return download_request
        if wait:
            logger.info("Waiting for the download to be generated")
            t0 = monotonic()
            while monotonic() - t0 < 120:
                response = ndb.get_download_request(
                    request_id=download_request.request_id
                )
                download_request = DownloadRequestOutput.model_validate(response.json())  # type: ignore
                if download_request.download_url is not None:
                    break
                sleep(5)
            return download_request

    @kb
    def download_status(
        self,
        request_id: str,
        **kwargs,
    ) -> DownloadRequestOutput:  # type: ignore
        """
        Get the current status of a download request.

        :param request_id: The ID of the download request.
        """
        ndb: NucliaDBClient = kwargs["ndb"]
        response = ndb.get_download_request(request_id=request_id)
        return DownloadRequestOutput.model_validate(response.json())  # type: ignore


class AsyncNucliaLogs:
    @kb
    async def query(
        self,
        *args,
        type: Union[EventType, str],
        query: Union[
            dict,
            ActivityLogsQuery,
            ActivityLogsSearchQuery,
            ActivityLogsAskQuery,
        ],
        **kwargs,
    ) -> ActivityLogsOutput:
        """
        Query activity logs.

        :param type: VISITED, MODIFIED, DELETED, NEW, SEARCH, SUGGEST, INDEXED, CHAT, ASK, STARTED, STOPPED, PROCESSED
        :param query: ActivityLogsQuery
        """
        _type = EventType[type.upper()] if isinstance(type, str) else type
        _query: Union[
            ActivityLogsQuery,
            ActivityLogsSearchQuery,
            ActivityLogsAskQuery,
        ]
        if isinstance(query, dict):
            if _type in (EventType.ASK, EventType.CHAT):  # TODO: deprecate chat event
                _query = ActivityLogsAskQuery.model_validate(query)
            elif type is EventType.SEARCH:
                _query = ActivityLogsSearchQuery.model_validate(query)
            else:
                _query = ActivityLogsQuery.model_validate(query)
        else:
            _query = query

        ndb: AsyncNucliaDBClient = kwargs["ndb"]
        response = await ndb.logs_query(type=_type, query=_query)
        output: list[ActivityLogsQueryResponse] = []  # type: ignore
        for line in response.iter_lines():
            output.append(ActivityLogsQueryResponse.model_validate_json(line))
        return ActivityLogsOutput(
            data=output, has_more=response.headers["has-more"].lower() == "true"
        )

    @kb
    async def download(
        self,
        *args,
        type: Union[EventType, str],
        query: Union[
            dict,
            DownloadActivityLogsQuery,
            DownloadActivityLogsSearchQuery,
            DownloadActivityLogsAskQuery,
        ],
        download_format: Union[DownloadFormat, str],
        wait: bool = False,
        **kwargs,
    ) -> DownloadRequestOutput:  # type: ignore
        """
        Download activity logs.

        :param type: VISITED, MODIFIED, DELETED, NEW, SEARCH, SUGGEST, INDEXED, CHAT, ASK, STARTED, STOPPED, PROCESSED
        :param download_format: NDJSON, CSV
        :param query: DownloadActivityLogsQuery
        """
        _type = EventType[type.upper()] if isinstance(type, str) else type
        _format = (
            DownloadFormat[download_format.upper()]
            if isinstance(download_format, str)
            else download_format
        )

        _query: Union[
            dict,
            DownloadActivityLogsQuery,
            DownloadActivityLogsSearchQuery,
            DownloadActivityLogsAskQuery,
        ]
        if isinstance(query, dict):
            if _type in (EventType.ASK, EventType.CHAT):  # TODO: deprecate chat event
                _query = DownloadActivityLogsAskQuery.model_validate(query)
            elif type is EventType.SEARCH:
                _query = DownloadActivityLogsSearchQuery.model_validate(query)
            else:
                _query = DownloadActivityLogsQuery.model_validate(query)
        else:
            _query = query

        ndb: AsyncNucliaDBClient = kwargs["ndb"]
        response = await ndb.logs_download(
            type=_type, query=_query, download_format=_format
        )

        download_request = DownloadRequestOutput.model_validate(response.json())  # type: ignore

        if not wait:
            return download_request
        if wait:
            logger.info("Waiting for the download to be generated")
            t0 = monotonic()
            while monotonic() - t0 < 120:
                response = await ndb.get_download_request(
                    request_id=download_request.request_id
                )
                download_request = DownloadRequestOutput.model_validate(response.json())  # type: ignore
                if download_request.download_url is not None:
                    break
                await asyncio.sleep(5)
            return download_request

    @kb
    async def download_status(
        self,
        request_id: str,
        **kwargs,
    ) -> DownloadRequestOutput:  # type: ignore
        """
        Get the current status of a download request.

        :param request_id: The ID of the download request.
        """
        ndb: AsyncNucliaDBClient = kwargs["ndb"]
        response = await ndb.get_download_request(request_id=request_id)
        return DownloadRequestOutput.model_validate(response.json())  # type: ignore
