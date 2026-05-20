from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

from nuclia.exceptions import NeedUserToken
from nuclia.sdk.kbs import AsyncNucliaKBS, NucliaKBS


def test_list_prefers_nua_when_no_user_token(monkeypatch):
    auth = Mock()
    config = Mock()
    config.token = None
    config.accounts = [SimpleNamespace(id="stale-account-id", slug="stale-account")]
    config.nuas_token = ["nua"]
    config.kbs_token = []
    config.get_default_nua.return_value = "default"
    config.get_nua.return_value = SimpleNamespace(account="nua-account-id")
    auth._config = config
    auth.accounts.side_effect = NeedUserToken()
    auth.kbs.side_effect = AssertionError(
        "sync user-token KB listing should not be used"
    )
    auth.kbs_nua.return_value = [SimpleNamespace(id="kb1")]

    monkeypatch.setattr("nuclia.sdk.kbs.get_auth", lambda: auth)
    monkeypatch.setattr("nuclia.decorators.get_auth", lambda: auth)

    result = NucliaKBS().list()

    assert [kb.id for kb in result] == ["kb1"]
    auth.kbs.assert_not_called()
    auth.kbs_nua.assert_called_once_with("nua-account-id")


@pytest.mark.asyncio
async def test_async_list_prefers_nua_when_no_user_token(monkeypatch):
    auth = Mock()
    config = Mock()
    config.token = None
    config.accounts = [SimpleNamespace(id="stale-account-id", slug="stale-account")]
    config.nuas_token = ["nua"]
    config.kbs_token = []
    config.get_default_nua.return_value = "default"
    config.get_nua.return_value = SimpleNamespace(account="nua-account-id")
    auth._config = config
    auth.accounts = AsyncMock(side_effect=NeedUserToken())
    auth.kbs = AsyncMock(
        side_effect=AssertionError("async user-token KB listing should not be used")
    )
    auth.kbs_nua = AsyncMock(return_value=[SimpleNamespace(id="kb1")])

    monkeypatch.setattr("nuclia.sdk.kbs.get_async_auth", lambda: auth)
    monkeypatch.setattr("nuclia.decorators.get_async_auth", lambda: auth)

    result = await AsyncNucliaKBS().list()

    assert [kb.id for kb in result] == ["kb1"]
    auth.kbs.assert_not_called()
    auth.kbs_nua.assert_awaited_once_with("nua-account-id")
