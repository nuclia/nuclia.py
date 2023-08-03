from nuclia.sdk.accounts import NucliaAccounts
from nuclia.tests.fixtures import TESTING_ACCOUNT_SLUG


def test_list_accounts(testing_config):
    accounts = NucliaAccounts()
    all_accounts = accounts.list()
    assert TESTING_ACCOUNT_SLUG in [account.slug for account in all_accounts]
