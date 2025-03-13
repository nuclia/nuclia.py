import os
import tempfile

import pytest

from nuclia import BASE_DOMAIN
from nuclia.config import reset_config_file, set_config_file
from nuclia.sdk.auth import NucliaAuth

IS_PROD = False
if BASE_DOMAIN == "stashify.cloud":
    TESTING_ACCOUNT_SLUG = "eric-cicd"
    TESTING_KBID = "3fc11430-e1d5-45c7-86de-86d8efdd2cac"
    TESTING_KB = "https://europe-1.stashify.cloud/api/v1/kb/" + TESTING_KBID
else:
    IS_PROD = True
    TESTING_ACCOUNT_SLUG = "nuclia"
    TESTING_KBID = "18ab102c-a7db-4a35-b894-c20422b3b9f0"
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


@pytest.fixture(autouse=True)
def cleanup_auth():
    # sdk stores the client on DATA, so when running async tests, that gets tied to a function scope loop
    # and breaks all consequent tests...
    from nuclia import data

    data.DATA.async_auth = None
