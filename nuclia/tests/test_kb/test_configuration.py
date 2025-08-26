from nuclia.sdk.kb import NucliaKB, AsyncNucliaKB
import pytest


def test_configuration(testing_config):
    kb = NucliaKB()
    kb.get_configuration()
    kb.set_configuration(foo="bar")
    kb.update_configuration(bar="baz")


@pytest.mark.asyncio
async def test_configuration_async(testing_config):
    kb = AsyncNucliaKB()
    await kb.get_configuration()
    await kb.set_configuration(foo="bar")
    await kb.update_configuration(bar="baz")
