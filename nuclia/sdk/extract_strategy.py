from nuclia.data import get_auth, get_async_auth
from nuclia.decorators import kb, pretty
from nuclia.lib.kb import NucliaDBClient, AsyncNucliaDBClient
from nuclia.sdk.auth import NucliaAuth, AsyncNucliaAuth
from nuclia_models.config.proto import ExtractConfig
from typing import Dict


class NucliaExtractStrategy:
    @property
    def _auth(self) -> NucliaAuth:
        auth = get_auth()
        return auth

    @kb
    @pretty
    def list(self, *args, **kwargs) -> Dict[str, ExtractConfig]:
        """
        List extract strategies
        """
        ndb: NucliaDBClient = kwargs["ndb"]
        response = ndb.list_extract_strategies()
        return response.json()

    @kb
    def add(
        self,
        *args,
        config: ExtractConfig,
        **kwargs,
    ) -> str:
        """
        Add extract strategy

        :param config: strategy configuration
        """
        if isinstance(config, dict):
            config = ExtractConfig.model_validate(config)

        ndb: NucliaDBClient = kwargs["ndb"]
        response = ndb.add_extract_strategy(config=config)
        return response.json()

    @kb
    def delete(self, *args, id: str, **kwargs):
        """
        Delete extract strategy

        :param id: ID of the strategy to delete
        """
        ndb: NucliaDBClient = kwargs["ndb"]
        ndb.delete_extract_strategy(strategy_id=id)


class AsyncNucliaExtractStrategy:
    @property
    def _auth(self) -> AsyncNucliaAuth:
        auth = get_async_auth()
        return auth

    @kb
    @pretty
    async def list(self, *args, **kwargs) -> Dict[str, ExtractConfig]:
        """
        List extract strategies
        """
        ndb: AsyncNucliaDBClient = kwargs["ndb"]
        response = await ndb.list_extract_strategies()
        return response.json()

    @kb
    async def add(
        self,
        *args,
        config: ExtractConfig,
        **kwargs,
    ) -> str:
        """
        Add extract strategy

        :param config: strategy configuration
        """
        if isinstance(config, dict):
            config = ExtractConfig.model_validate(config)

        ndb: AsyncNucliaDBClient = kwargs["ndb"]
        response = await ndb.add_extract_strategy(config=config)
        return response.json()

    @kb
    async def delete(self, *args, id: str, **kwargs):
        """
        Delete extract strategy

        :param id: ID of the strategy to delete
        """
        ndb: AsyncNucliaDBClient = kwargs["ndb"]
        await ndb.delete_extract_strategy(strategy_id=id)
