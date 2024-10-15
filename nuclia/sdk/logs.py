from nuclia.decorators import kb
from nuclia.lib.kb import LogType, NucliaDBClient
from nuclia_models.events.activity_logs import ActivityLogsQuery
from nuclia.lib.models import ActivityLogsOutput
from typing import Union


class NucliaLogs:
    @kb
    def get(
        self, *args, type: Union[LogType, str], month: str, **kwargs
    ) -> list[list[str]]:
        """
        Download activity logs.

        :param type: VISITED, MODIFIED, DELETED, NEW, SEARCH, SUGGEST, INDEXED, CHAT, STARTED, STOPPED, PROCESSED
        :param month: YYYY-MM
        """
        if isinstance(type, str):
            type = LogType[type.upper()]

        ndb: NucliaDBClient = kwargs["ndb"]
        resp = ndb.logs(type=type, month=month)
        return resp

    @kb
    def query(
        self,
        *args,
        type: Union[LogType, str],
        query: Union[dict, ActivityLogsQuery],
        **kwargs,
    ) -> ActivityLogsOutput:
        """
        Query activity logs.

        :param type: VISITED, MODIFIED, DELETED, NEW, SEARCH, SUGGEST, INDEXED, CHAT, STARTED, STOPPED, PROCESSED
        :param query: ActivityLogsQuery
        """
        if isinstance(type, str):
            type = LogType[type.upper()]

        ndb: NucliaDBClient = kwargs["ndb"]
        response = ndb.logs_query(type=type, query=query)
        output: list[ActivityLogsOutput] = []
        for line in response.iter_lines():
            output.append(ActivityLogsOutput.model_validate_json(line))
        return ActivityLogsOutput(
            data=output, has_more=bool(response.headers["has-more"])
        )
