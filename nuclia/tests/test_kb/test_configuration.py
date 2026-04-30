import pytest
from nucliadb_sdk.v2 import exceptions as nucliadb_exceptions

from nuclia.sdk.kb import AsyncNucliaKB, NucliaKB

ConfigurationValidationError: type[Exception] = getattr(
    nucliadb_exceptions, "UnprocessableEntity", nucliadb_exceptions.UnknownError
)


def test_configuration(testing_config):
    kb = NucliaKB()
    kb.get_configuration()

    # Should raise a 422 error because the configuration payload is invalid,
    # but it's ok as we are only testing the library here.
    with pytest.raises(ConfigurationValidationError) as err:
        kb.update_configuration(
            generative_model="foobar",
            semantic_model="bar",
            visual_labeling="yes",
            anonymization_model="I do not exist either",
            ner_model="neither do I",
        )
    assert "semantic_model" in str(err.value) or "422" in str(err.value)


@pytest.mark.asyncio
async def test_configuration_async(testing_config):
    kb = AsyncNucliaKB()
    await kb.get_configuration()

    # Should raise a 422 error because the configuration payload is invalid,
    # but it's ok as we are only testing the library here.
    with pytest.raises(ConfigurationValidationError) as err:
        await kb.update_configuration(
            generative_model="foobar",
            semantic_model="bar",
            visual_labeling="yes",
            anonymization_model="I do not exist either",
            ner_model="neither do I",
        )
    assert "semantic_model" in str(err.value) or "422" in str(err.value)
