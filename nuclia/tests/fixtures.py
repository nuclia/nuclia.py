import os
import pytest

TESTING_KB = (
    "https://europe-1.nuclia.cloud/api/v1/kb/eb720a59-f879-4b23-a995-605f91c874f4"
)


@pytest.fixture(scope="session")
def testing_user():
    return os.environ.get("GA_TESTING_TOKEN")


@pytest.fixture(scope="session")
def testing_nua():
    return os.environ.get("GA_TESTING_NUA")


@pytest.fixture(scope="session")
def testing_kb():
    return TESTING_KB, os.environ.get("GA_TESTING_SERVICE_TOKEN")
