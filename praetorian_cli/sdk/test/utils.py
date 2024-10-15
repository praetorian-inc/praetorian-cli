import os
import time
from random import randint
from subprocess import run

from praetorian_cli.sdk.chariot import Chariot
from praetorian_cli.sdk.keychain import Keychain
from praetorian_cli.sdk.model.utils import risk_key, asset_key, attribute_key


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
    o.risk_name = f'test-risk-name-{epoch_micro()}'
    o.risk_key = risk_key(o.asset_dns, o.risk_name)
    o.comment = f'Test comment {epoch_micro()}'
    o.attribute_name = f'test-attribute-name-{epoch_micro()}'
    o.attribute_value = f'test-attribute-value-{epoch_micro()}'
    o.asset_attribute_key = attribute_key(o.attribute_name, o.attribute_value, o.asset_key)
    o.email = f'test_email_{epoch_micro()}@example-{epoch_micro()}.com'
    return o


def clean_test_entities(sdk, o):
    for a in sdk.assets.attributes(o.asset_key):
        sdk.attributes.delete(a['key'])
    for a in sdk.assets.attributes(o.risk_key):
        sdk.attributes.delete(a['key'])
    sdk.risks.delete(o.risk_key)
    sdk.assets.delete(o.asset_key)


def verify_cli(command, expected_stdout=[], expected_stderr=[], ignore_stdout=False):
    result = run(f'praetorian chariot {command}', capture_output=True, text=True, shell=True)
    if expected_stdout:
        for out in expected_stdout:
            assert out in result.stdout, f'CLI "{command}" does not contain {out} in stdout; instead, got {result.stdout}'
    else:
        if not ignore_stdout:
            assert len(result.stdout) == 0, \
                f'CLI "{command}" should not have content in stdout; instead, got {result.stdout}'

    if expected_stderr:
        for err in expected_stderr:
            assert err in result.stderr, f'CLI "{command}" of CLI does not contain {out} in stderr; instead, got {result.stderr}'
    else:
        assert len(result.stderr) == 0, \
            f'CLI "{command}" should not have content in stderr; instead, got {result.stderr}'


def setup_chariot():
    return Chariot(Keychain(os.environ.get('CHARIOT_TEST_PROFILE')))
