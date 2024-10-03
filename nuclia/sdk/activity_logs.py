from nuclia.decorators import kb
from nuclia.lib.kb import LogType, NucliaDBClient
from nuclia.lib.models import ActivityLogsQuery
from typing import Union
import json


class NucliaActivityLogs:
    @kb
    def query(
        self,
        *args,
        type: LogType,
        query: Union[dict, ActivityLogsQuery],
        **kwargs,
    ) -> dict:
        """
        Query activity logs.

        :param type: VISITED, MODIFIED, DELETED, NEW, SEARCH, SUGGEST, INDEXED, CHAT, STARTED, STOPPED, PROCESSED
        """
        ndb: NucliaDBClient = kwargs["ndb"]
        response = ndb.logs_query(type=type, query=query)
        output = []
        for line in response.iter_lines():
            output.append(json.loads(line))
        return {"data": output, "has_more": bool(response.headers["has-more"])}
