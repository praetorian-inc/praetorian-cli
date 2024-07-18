from praetorian_cli.sdk.chariot import Chariot


class Attribute:
    def __init__(self, client: Chariot, attributeKey: str = None):
        super().__init__()
        self.client = client
        self.attributeKey = attributeKey
        self.attributeDetails = None
        self.sourceKey = None
        self.details()

    def details(self) -> dict:
        if self.attributeKey is not None:
            self.attributeDetails = self.client.my(dict(key=f'#attribute#{self.attributeKey}'))['attributes'][0]
            self.sourceKey = self.attributeDetails['source']

        return None if self.attributeKey is None else self.attributeDetails

    def add(self, source, name, value) -> list[dict]:
        return self.client.add('attribute', dict(key=source, name=name, value=value))['attributes']
