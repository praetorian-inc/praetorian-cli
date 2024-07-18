from praetorian_cli.handlers.utils import AssetPriorities
from praetorian_cli.sdk.chariot import Chariot
from praetorian_cli.sdk.attribute import Attribute
from praetorian_cli.sdk.risk import Risk


class Asset:
    def __init__(self, client: Chariot, assetKey: str = None):
        super().__init__()
        self.client = client
        self.assetKey = assetKey
        self.assetDetails = None

    def add(self, name, dns, priority) -> dict:
        if priority not in AssetPriorities.keys():
            raise ValueError(f'Invalid priority {priority}. Must be one of {AssetPriorities.keys()}')
        self.assetDetails = self.client.add('asset', dict(name=name, dns=dns, status=AssetPriorities[priority]))[0]
        self.assetKey = self.assetDetails['key']
        return self.assetDetails

    def details(self) -> dict:
        if not self.assetDetails:
            try:
                self.assetDetails = self.client.my(dict(key=self.assetKey))['assets'][0]
            except Exception as e:
                raise f'Error fetching asset details: {e}'
        return self.assetDetails

    def attributes(self) -> list:
        print(self.client.my(dict(source=self.assetKey)))
        return ()

    def add_risk(self, new_risk: Risk) -> Risk:
        return self.client.add('risk', dict(key=self.assetKey, name=new_risk.name, status=new_risk.status,
                                            comment=new_risk.comment))[0]

    def add_attribute(self, name, value) -> list[dict]:
        attr = Attribute(self.client)
        return attr.add(self.assetKey, name, value)

    def update(self, status) -> dict:
        self.assetDetails = self.client.update('asset', dict(key=self.assetKey, status=AssetPriorities[status]))[0]
        return self.assetDetails

    def delete(self) -> None:
        self.client.delete('asset', key=self.assetKey)
        self.assetDetails = None
        self.assetKey = None
