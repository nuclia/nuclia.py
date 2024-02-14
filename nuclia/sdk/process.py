from typing import Optional

from nucliadb_protos.writer_pb2 import BrokerMessage

from nuclia.data import get_auth
from nuclia.decorators import nua
from nuclia.lib.nua import NuaClient
from nuclia.lib.nua_responses import (
    ProcessRequestStatusResults,
)
from nuclia.sdk.auth import NucliaAuth


class NucliaProcessing:
    @property
    def _auth(self) -> NucliaAuth:
        auth = get_auth()
        return auth

    @nua
    def process_file(
        self,
        path: str,
        kbid: Optional[str] = None,
        timeout: Optional[int] = 30,
        **kwargs
    ) -> Optional[BrokerMessage]:
        nc: NuaClient = kwargs["nc"]
        response = nc.process_file(path, kbid)
        payload = nc.wait_for_processing(response, timeout=timeout)
        return payload

    @nua
    def status(self, **kwargs) -> ProcessRequestStatusResults:
        nc: NuaClient = kwargs["nc"]
        return nc.processing_status()
