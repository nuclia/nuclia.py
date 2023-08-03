from nuclia.sdk.kbs import NucliaKBS
from uuid import uuid4

from nuclia.tests.fixtures import TESTING_ACCOUNT_SLUG, TESTING_KBID

NEW_KB_SLUG = "testkb-" + uuid4().hex

def test_list_kbs(testing_config):
    kbs = NucliaKBS()
    all = kbs.list()
    assert TESTING_KBID in [kb.id for kb in all]

def test_add_kb(testing_config):
    kbs = NucliaKBS()
    kb = kbs.add(account=TESTING_ACCOUNT_SLUG, slug=NEW_KB_SLUG, title="Test KB")
    assert kb["id"] is not None
    assert kb["slug"] == NEW_KB_SLUG
    assert kb["title"] == "Test KB"

def test_delete_kb(testing_config):
    kbs = NucliaKBS()
    kbs.delete(account=TESTING_ACCOUNT_SLUG, slug=NEW_KB_SLUG)
    all = kbs.list()
    assert NEW_KB_SLUG not in [kb.slug for kb in all]