class Accounts:
    """ The methods in this class are to be assessed from sdk.accounts, where sdk is an instance
        of Chariot. """

    def __init__(self, api):
        self.api = api

    def get(self, key):
        """
        Get details of an account by its exact key.

        :param key: The exact key of the account to retrieve
        :type key: str
        :return: The matching account entity or None if not found
        :rtype: dict or None
        """
        return self.api.search.by_exact_key(key)

    def list(self, username_filter='', offset=None, pages=100000):
        """
        List accounts of collaborators and master accounts that the current principal can access.

        Optionally filtered by username of the collaborators or the authorized accounts.
        Filters out integration accounts (those without '@' in member field).

        :param username_filter: Filter results by username of collaborators or authorized accounts
        :type username_filter: str
        :param offset: The offset of the page you want to retrieve results
        :type offset: str or None
        :param pages: The number of pages of results to retrieve. <mcp>Start with one page of results unless specifically requested.</mcp>
        :type pages: int
        :return: A tuple containing (list of matching account entities, next page offset)
        :rtype: tuple
        """
        results, next_offset = self.api.search.by_key_prefix(f'#account#', offset, pages)

        # filter out the integrations
        results = [i for i in results if '@' in i['member']]

        # filter for user emails
        if username_filter:
            results = [i for i in results if username_filter == i['name'] or username_filter == i['member']]

        return results, next_offset

    def add_collaborator(self, collaborator_email):
        """
        Add a collaborator to the account of the current principal.

        :param collaborator_email: Email address of the collaborator to add
        :type collaborator_email: str
        :return: The created account entity with member information
        :rtype: dict
        """
        return self.api.link_account(collaborator_email)

    def delete_collaborator(self, collaborator_email):
        """
        Delete a collaborator from the account of the current principal.

        :param collaborator_email: Email address of the collaborator to remove
        :type collaborator_email: str
        :return: The deleted account entity with member information
        :rtype: dict
        """
        return self.api.unlink(collaborator_email)

    def collaborators(self):
        """
        Return emails of all users that are collaborating with the current principal.

        The current principal can be an assume-role account.

        :return: List of collaborator email addresses
        :rtype: list
        """
        accounts, _ = self.list()
        return [a['member'] for a in accounts if a['name'] == self.current_principal()]

    def authorized_accounts(self):
        """
        Return emails of all users that the current principal is authorized to access.

        The current principal can be an assume-role account.

        :return: List of authorized account email addresses
        :rtype: list
        """
        accounts, _ = self.list()
        return [a['name'] for a in accounts if a['member'] == self.current_principal()]

    def assume_role(self, account_email):
        """
        Switch session to assume-role account.

        :param account_email: Email address of the account to assume role into
        :type account_email: str
        :return: None
        :rtype: None
        """
        self.api.keychain.assume_role(account_email)

    def unassume_role(self):
        """
        Switch back to the login principal account.

        :return: None
        :rtype: None
        """
        self.api.keychain.unassume_role()

    def current_principal(self):
        """
        Tell you which account the current session is operating on.

        Returns the assume-role account if one is active, otherwise the login principal.

        :return: Email address of the current principal account
        :rtype: str
        """
        return self.api.keychain.account if self.api.keychain.account else self.api.keychain.username()

    def login_principal(self):
        """
        Tell you the user account that is used to login, regardless of assume-role account.

        :return: Email address of the login principal account
        :rtype: str
        """
        return self.api.keychain.username()
