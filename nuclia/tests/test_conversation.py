import os
from nuclia.sdk.kb import NucliaKB

from nuclia.sdk.upload import NucliaUpload

path = f"{os.path.dirname(__file__)}/assets/conversation.json"


def test_conversation(testing_config):
    nkb = NucliaKB()
    res = nkb.get_resource_by_slug(slug="conversation1")

    if res:
        nkb.delete(rid=res.id)
    nu = NucliaUpload()
    nu.conversation(path=path)
    res = nkb.list()
    assert res
