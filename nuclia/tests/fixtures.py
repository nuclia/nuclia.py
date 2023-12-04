import os
import tempfile

import pytest

from nuclia import BASE_DOMAIN
from nuclia.config import reset_config_file, set_config_file
from nuclia.sdk.auth import NucliaAuth

IS_PROD = False
if BASE_DOMAIN == "stashify.cloud":
    TESTING_ACCOUNT_SLUG = "eric-cicd"
    TESTING_KBID = "84379bd4-41d4-4100-86a2-9e5512675ae3"
    TESTING_KB = "https://europe-1.stashify.cloud/api/v1/kb/" + TESTING_KBID
else:
    IS_PROD = True
    TESTING_ACCOUNT_SLUG = "nuclia"
    TESTING_KBID = "eb720a59-f879-4b23-a995-605f91c874f4"
    TESTING_KB = "https://europe-1.nuclia.cloud/api/v1/kb/" + TESTING_KBID


@pytest.fixture(scope="module")
def testing_user():
    return os.environ.get("GA_TESTING_TOKEN")


@pytest.fixture(scope="module")
def testing_nua():
    return os.environ.get("GA_TESTING_NUA")


@pytest.fixture(scope="module")
def testing_kb():
    return os.environ.get("GA_TESTING_SERVICE_TOKEN")


@pytest.fixture(scope="module")
def testing_config(testing_kb, testing_nua, testing_user):
    os.environ["TESTING"] = "True"
    with tempfile.NamedTemporaryFile() as temp_file:
        temp_file.write(b"{}")
        temp_file.flush()
        set_config_file(temp_file.name)
        nuclia_auth = NucliaAuth()
        nuclia_auth.set_user_token(testing_user)
        nuclia_auth.kb(TESTING_KB, testing_kb)
        client_id = nuclia_auth.nua(testing_nua)
        assert client_id
        nuclia_auth._config.set_default_kb(TESTING_KBID)
        nuclia_auth._config.set_default_nua(client_id)

    yield
    reset_config_file()
