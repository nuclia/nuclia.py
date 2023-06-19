from typing import Tuple
from nuclia.sdk.auth import NucliaAuth


def test_auth_user(testing_user: str):
    pass


def test_auth_kb(testing_kb: Tuple[str, str]):
    na = NucliaAuth()
    url, token = testing_kb
    assert na.validate_kb(url, token)


def test_auth_nua(testing_nua: str):
    pass
    # na = NucliaAuth()
    # assert na.validate_nua("europe-1", testing_nua)
