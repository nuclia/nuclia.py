from typing import Optional

from nuclia.data import get_auth
from nuclia.decorators import nua
from nuclia.lib.nua import NuaClient
from nuclia.lib.nua_responses import LearningConfig, ProcessingStatus
from nuclia.sdk.auth import NucliaAuth
from nucliadb_protos.writer_pb2 import BrokerMessage


class NucliaProcessing:
    @property
    def _auth(self) -> NucliaAuth:
        auth = get_auth()
        return auth

    @nua
    def process_file(
        self, path: str, config: Optional[LearningConfig] = None, **kwargs
    ) -> Optional[BrokerMessage]:
        nc: NuaClient = kwargs["nc"]
        response = nc.process_file(path, config)
        payload = nc.wait_for_processing(response)
        return payload

    @nua
    def status(self, **kwargs) -> ProcessingStatus:
        nc: NuaClient = kwargs["nc"]
        return nc.processing_status()
