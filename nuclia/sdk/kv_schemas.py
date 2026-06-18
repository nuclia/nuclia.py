from nucliadb_models.kv_schemas import KBKVSchemas, KVSchema, UpdateKVSchema

from nuclia.data import get_async_auth, get_auth
from nuclia.decorators import kb
from nuclia.lib.kb import AsyncNucliaDBClient, NucliaDBClient
from nuclia.sdk.auth import AsyncNucliaAuth, NucliaAuth


class NucliaKVSchemas:
    @property
    def _auth(self) -> NucliaAuth:
        return get_auth()

    @kb
    def list(self, *args, **kwargs) -> KBKVSchemas:
        """
        List all KV schemas in the knowledge box
        """
        ndb: NucliaDBClient = kwargs["ndb"]
        return ndb.ndb.list_kv_schemas(kbid=ndb.kbid)

    @kb
    def get(self, *args, schema_id: str, **kwargs) -> KVSchema:
        """
        Get a KV schema by ID

        :param schema_id: ID of the schema to retrieve
        """
        ndb: NucliaDBClient = kwargs["ndb"]
        return ndb.ndb.get_kv_schema(kbid=ndb.kbid, schema_id=schema_id)

    @kb
    def create(self, *args, schema: KVSchema, **kwargs) -> KVSchema:
        """
        Create a new KV schema

        :param schema: KVSchema definition
        """
        if isinstance(schema, dict):
            schema = KVSchema.model_validate(schema)
        ndb: NucliaDBClient = kwargs["ndb"]
        return ndb.ndb.create_kv_schema(kbid=ndb.kbid, content=schema)

    @kb
    def update(
        self, *args, schema_id: str, schema: UpdateKVSchema, **kwargs
    ) -> KVSchema:
        """
        Update an existing KV schema

        :param schema_id: ID of the schema to update
        :param schema: Updated KVSchema fields (description and/or fields)
        """
        if isinstance(schema, dict):
            schema = UpdateKVSchema.model_validate(schema)
        ndb: NucliaDBClient = kwargs["ndb"]
        return ndb.ndb.update_kv_schema(
            kbid=ndb.kbid, schema_id=schema_id, content=schema
        )

    @kb
    def delete(self, *args, schema_id: str, **kwargs):
        """
        Delete a KV schema

        :param schema_id: ID of the schema to delete
        """
        ndb: NucliaDBClient = kwargs["ndb"]
        ndb.ndb.delete_kv_schema(kbid=ndb.kbid, schema_id=schema_id)


class AsyncNucliaKVSchemas:
    @property
    def _auth(self) -> AsyncNucliaAuth:
        return get_async_auth()

    @kb
    async def list(self, *args, **kwargs) -> KBKVSchemas:
        """
        List all KV schemas in the knowledge box
        """
        ndb: AsyncNucliaDBClient = kwargs["ndb"]
        return await ndb.ndb.list_kv_schemas(kbid=ndb.kbid)

    @kb
    async def get(self, *args, schema_id: str, **kwargs) -> KVSchema:
        """
        Get a KV schema by ID

        :param schema_id: ID of the schema to retrieve
        """
        ndb: AsyncNucliaDBClient = kwargs["ndb"]
        return await ndb.ndb.get_kv_schema(kbid=ndb.kbid, schema_id=schema_id)

    @kb
    async def create(self, *args, schema: KVSchema, **kwargs) -> KVSchema:
        """
        Create a new KV schema

        :param schema: KVSchema definition
        """
        if isinstance(schema, dict):
            schema = KVSchema.model_validate(schema)
        ndb: AsyncNucliaDBClient = kwargs["ndb"]
        return await ndb.ndb.create_kv_schema(kbid=ndb.kbid, content=schema)

    @kb
    async def update(
        self, *args, schema_id: str, schema: UpdateKVSchema, **kwargs
    ) -> KVSchema:
        """
        Update an existing KV schema

        :param schema_id: ID of the schema to update
        :param schema: Updated KVSchema fields (description and/or fields)
        """
        if isinstance(schema, dict):
            schema = UpdateKVSchema.model_validate(schema)
        ndb: AsyncNucliaDBClient = kwargs["ndb"]
        return await ndb.ndb.update_kv_schema(
            kbid=ndb.kbid, schema_id=schema_id, content=schema
        )

    @kb
    async def delete(self, *args, schema_id: str, **kwargs):
        """
        Delete a KV schema

        :param schema_id: ID of the schema to delete
        """
        ndb: AsyncNucliaDBClient = kwargs["ndb"]
        await ndb.ndb.delete_kv_schema(kbid=ndb.kbid, schema_id=schema_id)
