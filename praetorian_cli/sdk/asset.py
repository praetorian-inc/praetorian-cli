from praetorian_cli.sdk.chariot_client import ChariotClient


class Asset:
    def __init__(self, client: ChariotClient):
        super().__init__()
        self.client = client

    def get(self, asset_id: str) -> {}:
        resp = self.client.my({'key': asset_id})
        return resp

    def get_all(self) -> {}:
        resp = self.client.my({'key': '#asset#'})
        return resp

    def create(self, asset: dict) -> {}:
        resp = self.client.add('asset', asset)
        return resp
