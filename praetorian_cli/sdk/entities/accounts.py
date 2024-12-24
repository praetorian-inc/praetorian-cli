class Accounts:
    """ The methods in this class are to be assessed from sdk.accounts, where sdk is an instance
        of Chariot. """

    def __init__(self, api):
        self.api = api

    def get(self, key):
        """ Get details of an account """
        return self.api.search.by_exact_key(key)

    def list(self, username_filter='', offset=None, pages=10000):
        """ List accounts of collaborators and also list the master accounts that the current
            principal can access.

            Optionally filtered by username of the collaborators or the authorized accounts.
        """
        results, next_offset = self.api.search.by_key_prefix(f'#account#', offset, pages)

        # filter out the integrations
        results = [i for i in results if '@' in i['member']]

        # filter for user emails
        if username_filter:
            results = [i for i in results if username_filter == i['name'] or username_filter == i['member']]

        return results, next_offset

    def add_collaborator(self, collaborator_email):
        """ Add a collaborator to the account of the current principal """
        return self.api.link_account(collaborator_email)

    def delete_collaborator(self, collaborator_email):
        """ Delete a collaborator of the account of the current principal """
        return self.api.unlink(collaborator_email)

    def collaborators(self):
        """ return emails of all users that are collaborating with the current
            principal. The current principal can be an assume-role account. """
        accounts, _ = self.list()
        return [a['member'] for a in accounts if a['name'] == self.current_principal()]

    def authorized_accounts(self):
        """ return emails of all users that the current principal is authorized to access.
            The current principal can be an assume-role account. """
        accounts, _ = self.list()
        return [a['name'] for a in accounts if a['member'] == self.current_principal()]

    def assume_role(self, account_email):
        """ Switch session the assume-role account """
        self.api.keychain.assume_role(account_email)

    def unassume_role(self):
        """ Switch back to the login principal """
        self.api.keychain.unassume_role()

    def current_principal(self):
        """ Tell you which account the current session is operating on """
        return self.api.keychain.account if self.api.keychain.account else self.api.keychain.username()

    def login_principal(self):
        """ Tell you the user account that is used to login, regardless of who the current
            assume-role account is """
        return self.api.keychain.username()
