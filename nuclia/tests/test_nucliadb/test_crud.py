from asyncio import BaseEventLoop
from functools import partial

import pytest
from nucliadb_models.resource import KnowledgeBoxList, KnowledgeBoxObj, ResourceList
from nucliadb_sdk.tests.fixtures import NucliaFixture

from nuclia.sdk import NucliaAuth, NucliaDB, NucliaKB


@pytest.mark.asyncio
async def test_crud(nucliadb: NucliaFixture, event_loop: BaseEventLoop):
    auth = NucliaAuth()
    nkb = NucliaKB()
    ndb = NucliaDB()

    await event_loop.run_in_executor(
        None, auth.nucliadb, f"http://localhost:{nucliadb.port}"
    )

    listing_kbs: KnowledgeBoxList = await event_loop.run_in_executor(None, ndb.list)
    assert len(listing_kbs.kbs) == 0
    creation = partial(
        ndb.create,
        slug="kb",
        title="title",
        default=True,
    )

    kb_obj: KnowledgeBoxObj = await event_loop.run_in_executor(None, creation)
    assert kb_obj.slug == "kb"

    listing_kbs = await event_loop.run_in_executor(None, ndb.list)
    assert len(listing_kbs.kbs) == 1

    listing = partial(nkb.list, interactive=False)
    listing_res: ResourceList = await event_loop.run_in_executor(None, listing)
    assert len(listing_res.resources) == 0
