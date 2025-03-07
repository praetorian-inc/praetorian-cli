from urllib.parse import urlparse

import pytest
import requests

from praetorian_cli.sdk.model.globals import Risk
from praetorian_cli.sdk.model.utils import risk_key
from praetorian_cli.sdk.test.utils import make_test_values, clean_test_entities, setup_chariot


@pytest.mark.coherence
class TestWebhook:

    def setup_class(self):
        self.sdk = setup_chariot()
        make_test_values(self)

    def test_create_webhook(self):
        if self.sdk.webhook.get_record():
            self.sdk.webhook.delete()
        self.webhook = self.sdk.webhook.upsert()
        parsed_url = urlparse(self.webhook)

        assert all([parsed_url.scheme, parsed_url.netloc]), 'Webhook URL is not a valid URL'

    def test_add_asset(self):
        response = requests.put(url=self.sdk.webhook.get_url(), json=dict(dns=self.asset_dns, name=self.asset_name))
        assert response.status_code == 200, 'Webhook POST request failed'
        asset = self.sdk.assets.get(self.asset_key)
        assert asset != None
        attributes = self.sdk.assets.attributes(self.asset_key)
        assert len(attributes) == 1
        assert attributes[0]['name'] == 'source'
        assert attributes[0]['value'] == 'webhook'
        assert attributes[0]['source'] == self.asset_key
        self.sdk.assets.delete(self.asset_key)

    def test_add_risk(self):
        response = requests.put(url=self.sdk.webhook.get_url(),
                                json=dict(dns=self.asset_dns, name=self.asset_name, finding=self.risk_name))
        assert response.status_code == 200, 'Webhook POST request failed'
        risk = self.sdk.risks.get(risk_key(self.asset_dns, self.risk_name))
        assert risk != None
        attributes = self.sdk.risks.attributes(self.risk_key)
        assert len(attributes) == 1
        assert attributes[0]['name'] == 'source'
        assert attributes[0]['value'] == 'webhook'
        assert attributes[0]['source'] == self.risk_key
        self.sdk.risks.delete(self.risk_key, Risk.DELETED_DUPLICATE_CRITICAL.value)

    def test_delete_webhook(self):
        self.sdk.webhook.delete()
        assert self.sdk.webhook.get_record() == None

    def teardown_class(self):
        clean_test_entities(self.sdk, self)
