from typing import Optional

from nucliadb_protos.writer_pb2 import BrokerMessage

from nuclia.data import get_auth
from nuclia.decorators import nua
from nuclia.lib.nua import AsyncNuaClient, NuaClient
from nuclia.lib.nua_responses import ProcessRequestStatusResults
from nuclia.sdk.auth import NucliaAuth


class NucliaProcessing:
    @property
    def _auth(self) -> NucliaAuth:
        auth = get_auth()
        return auth

    @nua
    def process_file(
        self, path: str, kbid: str = "default", timeout: int = 300, **kwargs
    ) -> Optional[BrokerMessage]:
        nc: NuaClient = kwargs["nc"]
        response = nc.process_file(path, kbid)
        payload = nc.wait_for_processing(response, timeout=timeout)
        return payload

    @nua
    def process_link(
        self, url: str, kbid: Optional[str] = None, timeout: int = 300, **kwargs
    ) -> Optional[BrokerMessage]:
        nc: NuaClient = kwargs["nc"]
        response = nc.process_link(url, kbid)
        payload = nc.wait_for_processing(response, timeout=timeout)
        return payload

    @nua
    def status(self, **kwargs) -> ProcessRequestStatusResults:
        nc: NuaClient = kwargs["nc"]
        return nc.processing_status()


class AsyncNucliaProcessing:
    @property
    def _auth(self) -> NucliaAuth:
        auth = get_auth()
        return auth

    @nua
    async def process_file(
        self, path: str, kbid: Optional[str] = None, timeout: int = 300, **kwargs
    ) -> Optional[BrokerMessage]:
        nc: AsyncNuaClient = kwargs["nc"]
        response = await nc.process_file(path, kbid)
        payload = await nc.wait_for_processing(response, timeout=timeout)
        return payload

    @nua
    async def process_link(
        self, url: str, kbid: Optional[str] = None, timeout: int = 300, **kwargs
    ) -> Optional[BrokerMessage]:
        nc: AsyncNuaClient = kwargs["nc"]
        response = await nc.process_link(url, kbid)
        payload = await nc.wait_for_processing(response, timeout=timeout)
        return payload

    @nua
    async def status(self, **kwargs) -> ProcessRequestStatusResults:
        nc: AsyncNuaClient = kwargs["nc"]
        return await nc.processing_status()
