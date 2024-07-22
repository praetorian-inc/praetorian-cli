from praetorian_cli.sdk.chariot import Chariot
from praetorian_cli.sdk.chariot_response import ChariotResponse


class Attribute(ChariotResponse):
    def __init__(self, client: Chariot, attribute_key: str = None):
        super().__init__()
        self.client = client
        if attribute_key:
            attribute_details = self.client.my(dict(key=attribute_key))['attributes'][0]
            for key, value in attribute_details.items():
                setattr(self, key, value)

    def details(self) -> dict:
        return self.response()

    def add(self, source, name, value):
        attributes = self.client.add('attribute', dict(key=source, name=name, value=value))['attributes']
        if len(attributes) > 1:
            return [Attribute(self.client, attribute['key']) for attribute in attributes]
        else:
            return Attribute(self.client, attributes[0]['key'])
