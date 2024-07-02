import random

import pytest

from praetorian_cli.sdk.test import BaseTest


@pytest.mark.coherence
class TestLinkAccount(BaseTest):

    def setup_class(self):
        self.chariot, self.username = BaseTest.setup_chariot(self)
        self.link_account_name = f"chariot_cli_test_{random.randint(0, 9999)}@example.com"

    def test_link_account(self):
        response = self.chariot.link_account(username=self.link_account_name, config={})
        assert response['member'] == self.link_account_name
        my_accounts = self.chariot.my(dict(key=f'#account#{self.username}'))['accounts']
        assert any(account.get("member") == self.link_account_name for account in my_accounts)

    def test_unlink_account(self):
        response = self.chariot.unlink(username=self.link_account_name)
        assert response['member'] == self.link_account_name
        my_accounts = self.chariot.my(dict(key=f'#account#{self.username}'))['accounts']
        assert all(account.get("member") != self.link_account_name for account in my_accounts)
