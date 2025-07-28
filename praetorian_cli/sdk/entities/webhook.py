from base64 import b64encode
from uuid import uuid4


class Webhook:
    """ The methods in this class are to be assessed from sdk.webhook, where sdk is an instance
    of Chariot. """

    def __init__(self, api):
        self.api = api

    def upsert(self):
        """
        Create a new webhook integration for the account.

        Generates a unique PIN, links the account with the webhook integration,
        and returns the webhook URL that can be used to receive data. This method
        creates a new webhook endpoint that can accept JSON payloads containing
        asset and risk information.

        :return: The webhook URL that can be used to send data to this account
        :rtype: str

        **Example Usage:**
            >>> webhook_url = sdk.webhook.upsert()
            >>> print(f"Send data to: {webhook_url}")

        **Webhook Payload Format:**
            The webhook accepts JSON payloads with the following formats:

            Asset payload:
            ```json
            {
                "dns": "example.com",
                "name": "web-server",
                "source": "discovery-tool"
            }
            ```

            Risk payload:
            ```json
            {
                "dns": "example.com", 
                "name": "vulnerability-name",
                "source": "scanner-tool",
                "finding": "Description of the security finding"
            }
            ```
        """
        pin = str(uuid4())
        self.api.link_account('hook', pin)
        return self.webhook_url(pin)

    def get_url(self):
        """
        Get the URL of an existing webhook integration.

        Retrieves the webhook URL for the current account if a webhook integration
        exists. This method looks up the existing webhook record and constructs
        the URL using the stored PIN value.

        :return: The webhook URL if a webhook integration exists, None otherwise
        :rtype: str or None

        **Example Usage:**
            >>> webhook_url = sdk.webhook.get_url()
            >>> if webhook_url:
            ...     print(f"Existing webhook: {webhook_url}")
            ... else:
            ...     print("No webhook configured")
        """
        hook = self.get_record()
        return self.webhook_url(hook['value']) if hook else None

    def get_record(self):
        """
        Get the webhook integration record for the current account.

        Searches through the account's integrations to find the webhook integration
        record. The webhook integration is identified by having 'member' set to 'hook'.
        This record contains the PIN value and other webhook configuration details.

        :return: The webhook integration record containing 'key', 'member', 'value' fields, or None if no webhook exists
        :rtype: dict or None

        **Example Usage:**
            >>> hook_record = sdk.webhook.get_record()
            >>> if hook_record:
            ...     print(f"Webhook PIN: {hook_record['value']}")
            ...     print(f"Integration key: {hook_record['key']}")

        **Record Structure:**
            The returned record contains:
            - key: The integration key (format: #account#{username}#hook)
            - member: Always 'hook' for webhook integrations
            - value: The PIN used for webhook authentication
        """
        integrations, offset = self.api.integrations.list()
        for i in integrations:
            if i['member'] == 'hook':
                return i
        return None

    def delete(self):
        """
        Delete the webhook integration for the current account.

        Removes the webhook integration if it exists, effectively disabling the
        webhook endpoint. After deletion, the webhook URL will no longer accept
        incoming data and will return authentication errors.

        :return: The deleted webhook integration record if it existed, None if no webhook was configured
        :rtype: dict or None

        **Example Usage:**
            >>> deleted_hook = sdk.webhook.delete()
            >>> if deleted_hook:
            ...     print(f"Deleted webhook with PIN: {deleted_hook['value']}")
            ... else:
            ...     print("No webhook was configured to delete")

        **Security Note:**
            After deletion, any existing webhook URLs become invalid and will
            return HTTP 401 (Authentication failed) for incoming requests.
        """
        hook = self.get_record()
        if hook:
            self.api.delete_by_key('account/hook', hook['key'], dict(member='hook', value=hook['value']))
            return hook
        else:
            return None

    def webhook_url(self, pin):
        """
        Construct a webhook URL using the provided PIN.

        Creates a webhook URL by combining the base URL, base64-encoded username,
        and the provided PIN. This URL can be used to send JSON payloads containing
        asset and risk data to the Chariot platform.

        :param pin: The unique PIN for webhook authentication
        :type pin: str
        :return: The complete webhook URL for receiving data
        :rtype: str

        **Example Usage:**
            >>> url = sdk.webhook.webhook_url("abc123-def456")
            >>> print(f"Webhook URL: {url}")

        **URL Format:**
            The generated URL follows the format:
            `{base_url}/hook/{base64_username}/{pin}`

            Where:
            - base_url: The Chariot API base URL
            - base64_username: The account username encoded in base64 (padding removed)
            - pin: The unique PIN for this webhook integration

        **Authentication:**
            The webhook endpoint validates incoming requests by:
            1. Decoding the base64 username from the URL path
            2. Verifying the PIN matches the stored webhook integration
            3. Rejecting requests with invalid credentials (HTTP 401)
        """
        # Use current_principal() instead of username()
        username = b64encode(self.api.accounts.current_principal().encode('utf8'))
        return f'{self.api.keychain.base_url()}/hook/{username.decode("utf8").rstrip("=")}/{pin}'
