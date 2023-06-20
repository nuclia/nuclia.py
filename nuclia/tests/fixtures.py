import os
import tempfile

import pytest

from nuclia.config import reset_config_file, set_config_file
from nuclia.sdk.auth import NucliaAuth

TESTING_KBID = "eb720a59-f879-4b23-a995-605f91c874f4"
TESTING_KB = "https://europe-1.nuclia.cloud/api/v1/kb/" + TESTING_KBID


@pytest.fixture(scope="session")
def testing_user():
    return os.environ.get("GA_TESTING_TOKEN")


@pytest.fixture(scope="session")
def testing_nua():
    return os.environ.get("GA_TESTING_NUA")


@pytest.fixture(scope="session")
def testing_kb():
    return os.environ.get("GA_TESTING_SERVICE_TOKEN")


@pytest.fixture(scope="session")
def testing_config(testing_kb, testing_nua, testing_user):
    os.environ["TESTING"] = "True"
    with tempfile.NamedTemporaryFile() as temp_file:
        temp_file.write(b"{}")
        temp_file.flush()
        set_config_file(temp_file.name)
        nuclia_auth = NucliaAuth()
        nuclia_auth.set_user_token(testing_user)
        nuclia_auth.kb(TESTING_KB, testing_kb)
        client_id = nuclia_auth.nua("europe-1", testing_nua)
        nuclia_auth._config.set_default_kb(TESTING_KBID)
        nuclia_auth._config.set_default_nua(client_id)

        yield
        reset_config_file()
