from praetorian_cli.handlers.utils import AssetPriorities
from praetorian_cli.sdk.attribute import Attribute
from praetorian_cli.sdk.chariot import Chariot
from praetorian_cli.sdk.chariot_response import ChariotResponse


class Asset(ChariotResponse):
    def __init__(self, client: Chariot, asset_key: str = None):
        super().__init__()
        self.client = client
        if asset_key:
            asset_details = self.client.my(dict(key=asset_key))['assets'][0]
            for key, value in asset_details.items():
                setattr(self, key, value)

    def add(self, name, dns, priority):
        if priority not in AssetPriorities.keys():
            raise ValueError(f'Invalid priority {priority}. Must be one of {AssetPriorities.keys()}')
        asset_details = self.client.add('asset', dict(name=name, dns=dns, status=AssetPriorities[priority]))[0]
        for key, value in asset_details.items():
            setattr(self, key, value)

    def details(self) -> dict:
        return self.response()

    def attributes(self) -> list:
        return self.client.my(dict(key=f'source:{self.key}'))['attributes']

    def add_risk(self, name, status, comment) -> dict:
        risk_payload = dict(key=self.key, name=name, status=status, comment=comment)
        return self.client.add('risk', risk_payload)['risks'][0]

    def add_attribute(self, name, value):
        attr = Attribute(self.client)
        return attr.add(self.key, name, value)

    def update(self, status) -> dict:
        update = self.client.update('asset', dict(key=self.key, status=AssetPriorities[status]))[0]
        for key, value in update.items():
            setattr(self, key, value)

    def delete(self) -> None:
        self.client.delete('asset', key=self.key)
        self.__del__()

    def __del__(self):
        for key in self.__dict__.keys():
            if key != 'client':
                setattr(self, key, None)
