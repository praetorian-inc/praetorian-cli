from praetorian_cli.handlers.utils import AssetPriorities
from praetorian_cli.sdk.attribute import Attribute
from praetorian_cli.sdk.chariot import Chariot


class Asset:
    def __init__(self, client: Chariot, assetKey: str = None):
        super().__init__()
        self.client = client
        self.assetKey = assetKey

    def add(self, name, dns, priority) -> dict:
        if priority not in AssetPriorities.keys():
            raise ValueError(f'Invalid priority {priority}. Must be one of {AssetPriorities.keys()}')
        assetDetails = self.client.add('asset', dict(name=name, dns=dns, status=AssetPriorities[priority]))[0]
        self.assetKey = assetDetails['key']
        return assetDetails

    def details(self) -> dict:
        return self.client.my(dict(key=self.assetKey))['assets'][0]

    def attributes(self) -> list:
        return self.client.my(dict(key=f'source:{self.assetKey}'))['attributes']

    def add_risk(self, name, status, comment) -> dict:
        risk_payload = dict(key=self.assetKey, name=name, status=status, comment=comment)
        return self.client.add('risk', risk_payload)['risks'][0]

    def add_attribute(self, name, value) -> list[dict]:
        attr = Attribute(self.client)
        return attr.add(self.assetKey, name, value)

    def update(self, status) -> dict:
        return self.client.update('asset', dict(key=self.assetKey, status=AssetPriorities[status]))[0]

    def delete(self) -> None:
        self.client.delete('asset', key=self.assetKey)
        self.assetKey = None
