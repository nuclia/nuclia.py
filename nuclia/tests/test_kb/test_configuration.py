import pytest
from nucliadb_sdk.v2.exceptions import UnknownError

from nuclia.sdk.kb import AsyncNucliaKB, NucliaKB


def test_configuration(testing_config):
    kb = NucliaKB()
    kb.get_configuration()

    # Should raise 422 error because the generative_model "foobar" does not
    # exist, but it's ok as we are only testing the library here.
    with pytest.raises(UnknownError) as err:
        kb.update_configuration(
            generative_model="foobar",
            semantic_model="bar",
            visual_labeling="yes",
            anonymization_model="I do not exist either",
            ner_model="neither do I",
        )
    assert "422" in str(err.value)


@pytest.mark.asyncio
async def test_configuration_async(testing_config):
    kb = AsyncNucliaKB()
    await kb.get_configuration()

    # Should raise 422 error because the generative_model "foobar" does not
    # exist, but it's ok as we are only testing the library here.
    with pytest.raises(UnknownError) as err:
        await kb.update_configuration(
            generative_model="foobar",
            semantic_model="bar",
            visual_labeling="yes",
            anonymization_model="I do not exist either",
            ner_model="neither do I",
        )
    assert "422" in str(err.value)
