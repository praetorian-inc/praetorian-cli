from random import randint
from time import time

import pytest

from praetorian_cli.sdk.test import BaseTest
from praetorian_cli.sdk.test.models import asset_key
from praetorian_cli.sdk.test.utils import verify_cli


@pytest.fixture(scope="class", params=[f'contoso-{int(time() * 1000000)}.com'])
def asset(request):
    request.cls.asset = request.param


@pytest.mark.usefixtures("asset")
@pytest.mark.cli
class TestCli(BaseTest):
    def setup_class(self):
        self.asset_dns = f'contoso-{int(time() * 1000000)}.com'
        self.asset_name = f'{octet()}.{octet()}.{octet()}.{octet()}'
        self.asset_key = asset_key(self.asset_dns, self.asset_name)

    def test_add_asset(self):
        verify_cli(f'add asset --name {self.asset_name} --dns {self.asset_dns}')

    def test_list_asset(self):
        verify_cli('list assets', [self.asset_key])
        verify_cli('list assets --page no', [self.asset_key])
        verify_cli('list assets --page all', [self.asset_key])

        verify_cli('list assets --details', [self.asset_key, '"key"'])
        verify_cli('list assets --details --page no', [self.asset_key])
        verify_cli('list assets --details --page all', [self.asset_key])

        verify_cli(f'list assets --filter "{self.asset_dns}"', [self.asset_key])
        verify_cli(f'list assets --details --filter "{self.asset_dns}"', [self.asset_key, '"key"'])
        verify_cli(f'list assets --filter "{int(time() * 1000000)}"')

        verify_cli('list assets --plugin example', ['cli_kwargs'])
        verify_cli('list assets --details --plugin example', ['cli_kwargs', '"key"'])


def octet():
    return randint(1, 255)
