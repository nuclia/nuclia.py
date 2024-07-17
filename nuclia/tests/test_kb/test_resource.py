import warnings

from time import sleep

from nucliadb_sdk.v2.exceptions import NotFoundError

from nuclia.sdk.resource import NucliaResource


def test_resource(testing_config):
    nresource = NucliaResource()
    try:
        res = nresource.get(slug="res1")
        nresource.delete(rid=res.id)
    except NotFoundError:
        pass

    res_id = nresource.create(slug="res1")

    res = nresource.get(rid=res_id)
    assert res

    res = nresource.get(slug="res1")
    assert res
    assert res.id == res_id

    assert res.title == "res1"

    nresource.update(
        rid=res_id,
        title="My great resource",
        texts={"text1": {"body": "Hello here"}},
    )
    res = nresource.get(slug="res1", show=["basic", "values"])

    assert res
    assert res.title in ["My great resource", "res1"]
    if res.data.texts:
        assert res.data.texts["text1"]
    else:
        warnings.warn("No texts found in resource")

    nresource.delete(rid=res_id)

    try:
        sleep(0.5)
        nresource.get(slug="res1")
        assert False
    except NotFoundError:
        assert True
