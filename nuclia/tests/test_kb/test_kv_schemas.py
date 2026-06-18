from nucliadb_models.kv_schemas import KVSchema, KVSchemaField, UpdateKVSchema

from nuclia.sdk.kb import NucliaKB


def test_kv_schemas(testing_config):
    nkb = NucliaKB()

    # preventive clean up
    for schema_id in nkb.kv_schemas.list().schemas.keys():
        nkb.kv_schemas.delete(schema_id=schema_id)

    # create
    nkb.kv_schemas.create(
        schema=KVSchema(
            id="product",
            description="A product schema",
            fields=[
                KVSchemaField(key="color", type="text"),
                KVSchemaField(key="price", type="float"),
            ],
        )
    )

    all = nkb.kv_schemas.list()
    assert len(all.schemas) == 1
    assert "product" in all.schemas

    # get
    schema = nkb.kv_schemas.get(schema_id="product")
    assert schema.id == "product"
    assert schema.description == "A product schema"

    # update
    nkb.kv_schemas.update(
        schema_id="product",
        schema=UpdateKVSchema(description="Updated description"),
    )
    schema = nkb.kv_schemas.get(schema_id="product")
    assert schema.description == "Updated description"

    # delete
    nkb.kv_schemas.delete(schema_id="product")
    all = nkb.kv_schemas.list()
    assert len(all.schemas) == 0
