from nuclia.sdk.auth import NucliaAuth
from nuclia.tests.fixtures import TESTING_KB


def test_auth_user(testing_user: str):
    na = NucliaAuth()
    assert na._validate_user_token(testing_user)


def test_auth_kb(testing_kb: str):
    na = NucliaAuth()
    kbobj = na.validate_kb(TESTING_KB, testing_kb)
    assert kbobj
    assert kbobj.uuid
    assert kbobj.config
    assert kbobj.config.title


def test_auth_nua(testing_nua: str):
    na = NucliaAuth()
    client, account_type, account, region = na.validate_nua(testing_nua)
    assert client
    assert account_type
    assert account
