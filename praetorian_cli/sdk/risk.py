from praetorian_cli.sdk.attribute import Attribute
from praetorian_cli.sdk.chariot import Chariot
class Risk:
    def __init__(self, client: Chariot, riskKey: str = None):
        super().__init__()
        self.client = client
        self.riskKey = riskKey
        self.riskDetails = client.my(dict(key=f'#risk#{riskKey}'))['risks'][0]

    def details(self) -> dict:
        return self.riskDetails

    def attributes(self) -> list[Attribute]:
        response = self.client.my(dict(key=f'source:{self.riskKey}'))['attributes']
        attr_list = [Attribute(self.client, attribute['key']) for attribute in response]

        return attr_list

    def add_attribute(self, name, value) -> Attribute:
        return self.client.add('attribute', dict(key=self.riskKey, name=name, value=value))[0]