from nuclia.decorators import kb
from nuclia.lib.kb import LogType, NucliaDBClient


class NucliaLogs:
    @kb
    def get(self, *args, type: LogType, month: str, **kwargs) -> list[list[str]]:
        """
        Download activity logs.

        :param type: NEW, PROCESSED, MODIFIED, CHAT, SEARCH, FEEDBACK
        :param month: YYYY-MM
        """
        ndb: NucliaDBClient = kwargs["ndb"]
        resp = ndb.logs(type=type, month=month)
        return resp
