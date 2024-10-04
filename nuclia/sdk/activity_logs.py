from nuclia.decorators import kb
from nuclia.lib.kb import LogType, NucliaDBClient
from nuclia.lib.models import (
    ActivityLogsQuery,
    ActivityLogsQueryResponse,
    ActivityLogsOutput,
)
from typing import Union


class NucliaActivityLogs:
    @kb
    def query(
        self,
        *args,
        type: LogType,
        query: Union[dict, ActivityLogsQuery],
        **kwargs,
    ) -> ActivityLogsQueryResponse:
        """
        Query activity logs.

        :param type: VISITED, MODIFIED, DELETED, NEW, SEARCH, SUGGEST, INDEXED, CHAT, STARTED, STOPPED, PROCESSED
        """
        ndb: NucliaDBClient = kwargs["ndb"]
        response = ndb.logs_query(type=type, query=query)
        output: list[ActivityLogsOutput] = []
        for line in response.iter_lines():
            output.append(ActivityLogsOutput.model_validate_json(line))
        return ActivityLogsQueryResponse(
            data=output, has_more=bool(response.headers["has-more"])
        )
