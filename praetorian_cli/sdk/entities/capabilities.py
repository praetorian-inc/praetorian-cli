class Capabilities:
    """ The methods in this class are to be assessed from sdk.capabilities, where sdk is an instance
    of Chariot. """

    def __init__(self, api):
        self.api = api

    def list(self, name='', target='', executor='') -> tuple:
        """ List capabilities, optionally filtered by name, target, and/or executor """
        return self.api.get('capabilities', {'name': name, 'target': target, 'executor': executor})