class ChariotResponse:
    def __init__(self):
        self.username = None
        self.key = None
        self.source = None
        self.dns = None
        self.name = None
        self.status = None
        self.config = None
        self.created = None
        self.updated = None
        self.ttl = None
        self.history = None

    def response(self, ) -> dict:
        return {key: value for key, value in self.__dict__.items() if value is not None}
