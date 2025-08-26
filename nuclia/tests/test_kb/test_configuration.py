from nuclia.sdk.kb import NucliaKB, AsyncNucliaKB
import pytest
from nucliadb_sdk.v2.exceptions import UnknownError


def test_configuration(testing_config):
    kb = NucliaKB()
    kb.get_configuration()

    # Should raise 422 error because the generative_model "foobar" does not exist
    with pytest.raises(UnknownError) as err:
        kb.set_configuration(generative_model="foobar")
    assert "422" in str(err.value)


@pytest.mark.asyncio
async def test_configuration_async(testing_config):
    kb = AsyncNucliaKB()
    await kb.get_configuration()

    # Should raise 422 error because the generative_model "foobar" does not exist
    with pytest.raises(UnknownError) as err:
        await kb.set_configuration(generative_model="foobar")
    assert "422" in str(err.value)
