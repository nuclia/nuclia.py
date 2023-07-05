import os

from nucliadb_sdk.v2.exceptions import NotFoundError

from nuclia.sdk.kb import NucliaKB
from nuclia.sdk.upload import NucliaUpload

path = f"{os.path.dirname(__file__)}/assets/conversation.json"


def test_conversation(testing_config):
    nkb = NucliaKB()
    try:
        resource = nkb.get_resource_by_slug(slug="conversation1")
        nkb.delete(rid=resource.id)
    except NotFoundError:
        pass

    res = nkb.list()
    assert res is None

    nu = NucliaUpload()
    nu.conversation(path=path, slug="conversation1", field="c1")

    resource = nkb.get_resource_by_slug(slug="conversation1")
    assert resource
    assert resource.data.conversations["c1"]
