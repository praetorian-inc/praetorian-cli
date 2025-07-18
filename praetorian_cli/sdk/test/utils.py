import os
import time
from random import randint

from praetorian_cli.sdk.chariot import Chariot
from praetorian_cli.sdk.keychain import Keychain
from praetorian_cli.sdk.model.globals import Risk, Preseed
from praetorian_cli.sdk.model.utils import risk_key, asset_key, attribute_key, seed_key, preseed_key, setting_key, configuration_key


def epoch_micro():
    return int(time.time() * 1000000)


def random_ip():
    return f'10.{octet()}.{octet()}.{octet()}'


def octet():
    return randint(1, 256)


def random_dns():
    return f'test-{epoch_micro()}.com'


def make_test_values(o):
    o.asset_dns = random_dns()
    o.asset_name = random_ip()
    o.asset_key = asset_key(o.asset_dns, o.asset_name)
    o.seed_dns = random_dns()
    o.seed_key = seed_key('domain', o.seed_dns)
    o.risk_name = f'test-risk-name-{epoch_micro()}'
    o.risk_key = risk_key(o.asset_dns, o.risk_name)
    o.comment = f'Test comment {epoch_micro()}'
    o.attribute_name = f'test-attribute-name-{epoch_micro()}'
    o.attribute_value = f'test-attribute-value-{epoch_micro()}'
    o.asset_attribute_key = attribute_key(o.attribute_name, o.attribute_value, o.asset_key)
    o.email = email_address()
    o.preseed_type = f'test-preseed-type-{epoch_micro()}'
    o.preseed_title = f'test-preseed-title-{epoch_micro()}'
    o.preseed_value = f'test-preseed-value-{epoch_micro()}'
    o.preseed_status = Preseed.FROZEN.value
    o.preseed_key = preseed_key(o.preseed_type, o.preseed_title, o.preseed_value)
    o.setting_name = f'test-setting-name-{epoch_micro()}'
    o.setting_value = f'test-setting-value-{epoch_micro()}'
    o.setting_key = setting_key(o.setting_name)
    o.configuration_name = f'test-configuration-name-{epoch_micro()}'
    o.configuration_value = {o.configuration_name: o.configuration_name}
    o.configuration_key = configuration_key(o.configuration_name)
    o.key_name = f'test-key-name-{epoch_micro()}'
    return o


def clean_test_entities(sdk, o):
    for a in sdk.assets.attributes(o.asset_key):
        sdk.attributes.delete(a['key'])
    for a in sdk.assets.attributes(o.risk_key):
        sdk.attributes.delete(a['key'])
    sdk.risks.delete(o.risk_key, Risk.DELETED_DUPLICATE_CRITICAL.value)
    sdk.assets.delete(o.asset_key)
    sdk.settings.delete(o.setting_key)
    sdk.configurations.delete(o.configuration_key)

def setup_chariot():
    return Chariot(Keychain(os.environ.get('CHARIOT_TEST_PROFILE')))


def email_address():
    return f'test_email_{epoch_micro()}@example-{epoch_micro()}.com'
