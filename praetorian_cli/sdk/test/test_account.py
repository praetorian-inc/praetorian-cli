import pytest

from praetorian_cli.sdk.test.utils import setup_chariot, email_address


@pytest.mark.coherence
class TestAccount:

    def setup_class(self):
        self.sdk = setup_chariot()
        self.collaborator_email = email_address()

    def test_add_collaborator(self):
        account = self.sdk.accounts.add_collaborator(self.collaborator_email)
        assert account['member'] == self.collaborator_email
        accounts, _ = self.sdk.accounts.list()
        assert len(accounts) > 0
        assert any([a['member'] == self.collaborator_email for a in accounts])

    def test_delete_collaborator(self):
        account = self.sdk.accounts.delete_collaborator(self.collaborator_email)
        assert account['member'] == self.collaborator_email
        accounts, _ = self.sdk.accounts.list()
        assert all([a['member'] != self.collaborator_email for a in accounts])
