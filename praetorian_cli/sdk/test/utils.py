import os
import time
from random import randint

from praetorian_cli.sdk.chariot import Chariot
from praetorian_cli.sdk.keychain import Keychain
from praetorian_cli.sdk.model.globals import Risk, Preseed
from praetorian_cli.sdk.model.utils import risk_key, asset_key, ad_domain_key, attribute_key, seed_asset_key, preseed_key, setting_key, configuration_key


def epoch_micro():
    return int(time.time() * 1000000)


def random_ip():
    return f'10.{octet()}.{octet()}.{octet()}'


def octet():
    return randint(1, 256)


def random_dns():
    return f'test-{epoch_micro()}.com'


def random_ad_domain():
    return f'test-{epoch_micro()}.local'

def random_object_id():
    domain_id_1 = randint(1000000000, 4294967295)  # Start from 1 billion for realism
    domain_id_2 = randint(1000000000, 4294967295)
    domain_id_3 = randint(1000000000, 4294967295)

    # Generate a random relative identifier (RID)
    # Common ranges: 500-999 for built-in accounts, 1000+ for user accounts
    relative_id = randint(1000, 999999)
    return f"S-1-5-21-{domain_id_1}-{domain_id_2}-{domain_id_3}-{relative_id}"


def make_test_values(o):
    o.asset_dns = random_dns()
    o.asset_name = random_ip()
    o.asset_key = asset_key(o.asset_dns, o.asset_name)
    o.ad_domain_name = random_ad_domain()
    o.ad_object_id = random_object_id()
    o.ad_domain_key = ad_domain_key(o.ad_domain_name, o.ad_object_id)
    o.seed_asset_dns = random_dns()
    o.seed_asset_key = seed_asset_key(o.seed_asset_dns)
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
    o.webapp_name = f'test-webapp-name-{epoch_micro()}'
    o.webapp_url = f'https://test-webapp-{epoch_micro()}.com/'
    o.webapp_key = f'#webapplication#{o.webapp_url}'
    o.webpage_url = f'https://test-webpage-{epoch_micro()}.com/index.html'
    o.webpage_key = f'#webpage#{o.webpage_url}'
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
