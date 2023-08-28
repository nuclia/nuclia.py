import os

from nucliadb_sdk.v2.exceptions import NotFoundError

from nuclia.sdk.kb import NucliaKB
from nuclia.sdk.resource import NucliaResource
from nuclia.sdk.upload import NucliaUpload

path = f"{os.path.dirname(__file__)}/../assets/conversation.json"


def test_conversation(testing_config):
    nkb = NucliaKB()
    nresource = NucliaResource()
    try:
        res = nresource.get(slug="conversation1")
        nresource.delete(rid=res.id)
    except NotFoundError:
        pass

    res = nkb.list()
    assert res is None

    nu = NucliaUpload()
    nu.conversation(path=path, slug="conversation1", field="c1")

    res = nresource.get(slug="conversation1", show=["values"])
    assert res
    assert res.data.conversations["c1"]
