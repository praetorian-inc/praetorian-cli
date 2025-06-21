from praetorian_cli.sdk.model.globals import Kind


class Credentials:
    """ The methods in this class are to be accessed from sdk.credentials, where sdk is an instance
    of Chariot. """

    def __init__(self, api):
        self.api = api

    def list(self, offset=None, pages=100000):
        """ List credentials

        Arguments:
        offset: str
            The offset of the page you want to retrieve results. If this is not supplied,
            this function retrieves from the first page.
        pages: int
            The number of pages of results to retrieve.
        """
        return self.api.my('credentials', offset=offset, pages=pages)

    def get(self, credential_id, category, type, format, **parameters):
        """ Get a specific credential

        Arguments:
        credential_id: str
            The ID of the credential to retrieve
        category: str
            The category of the credential (e.g., 'integration', 'cloud')
        type: str
            The type of credential (e.g., 'aws', 'gcp', 'azure', 'static', 'ssh_key', 'json')
        format: str
            The format of the credential response
        **parameters: dict
            Additional parameters required for the credential request
        """
        request = {
            'CredentialID': credential_id,
            'Category': category,
            'Type': type,
            'Format': format,
            'Parameters': parameters
        }
        return self.api.post('broker', request)
