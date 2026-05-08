from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from nuclia.decorators import account


def test_account_prefers_nua_in_nua_only_mode(monkeypatch):
    auth = Mock()
    config = Mock()
    config.token = None
    config.nuas_token = ["nua"]
    config.get_default_nua.return_value = "default-nua"
    config.get_nua.return_value = SimpleNamespace(account="nua-account-id")
    auth._config = config

    monkeypatch.setattr("nuclia.decorators.get_auth", lambda: auth)

    @account
    def wrapped(**kwargs):
        return kwargs["account_id"]

    account_id = wrapped()

    assert account_id == "nua-account-id"
    auth.get_account_id.assert_not_called()


@pytest.mark.asyncio
async def test_async_account_prefers_nua_in_nua_only_mode(monkeypatch):
    auth = Mock()
    config = Mock()
    config.token = None
    config.nuas_token = ["nua"]
    config.get_default_nua.return_value = "default-nua"
    config.get_nua.return_value = SimpleNamespace(account="nua-account-id")
    auth._config = config

    monkeypatch.setattr("nuclia.decorators.get_async_auth", lambda: auth)

    @account
    async def wrapped(**kwargs):
        return kwargs["account_id"]

    account_id = await wrapped()

    assert account_id == "nua-account-id"
    auth.get_account_id.assert_not_called()
