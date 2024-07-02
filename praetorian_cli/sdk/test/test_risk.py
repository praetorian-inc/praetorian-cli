import time

import pytest

from praetorian_cli.sdk.test import BaseTest, utils


@pytest.mark.coherence
class TestRisk(BaseTest):
    test_id = int(time.time())
    asset_payload = dict(dns=f"contoso-{test_id}.com", name="10.1.1.5")
    risk_payload = dict(name=f"CVE-{test_id}", status="TI", comment=f"Test Risk at {test_id}")
    key = f"{asset_payload['dns']}#{risk_payload['name']}"

    def setup_class(self):
        self.chariot, self.username = BaseTest.setup_chariot(self)
        webhook = self.chariot.add_webhook()
        utils.add_asset_via_webhook(webhook, self.asset_payload)

    def test_add_risk(self):
        response = self.chariot.my(dict(key=f'#asset#{TestRisk.asset_payload["dns"]}'))
        assert response['assets'], "No assets found"
        TestRisk.risk_payload['key'] = response['assets'][0]['key']
        response = self.chariot.add('risk', TestRisk.risk_payload)['risks'][0]
        assert response['name'] == TestRisk.risk_payload['name']
        assert response['status'] == TestRisk.risk_payload['status']
        assert response['comment'] == TestRisk.risk_payload['comment']

    def test_my_risk(self):
        response = self.chariot.my(dict(key=f'#risk#{TestRisk.key}'))
        assert any(my_risk['name'] == TestRisk.risk_payload['name'] for my_risk in response['risks']), \
            "None of the risks matched self.risk_payload['name']"

    def test_update_risk(self):
        response = self.chariot.update('risk', dict(key=f'#risk#{TestRisk.key}', status='CI'))
        for risk in response['risks']:
            assert risk['status'] == 'CI'
            assert risk['name'] == TestRisk.risk_payload['name']
