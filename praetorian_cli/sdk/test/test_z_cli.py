import os

import pytest

from praetorian_cli.sdk.model.globals import AddRisk, Asset, Risk
from praetorian_cli.sdk.test.utils import verify_cli, epoch_micro, random_ip, make_test_values, clean_test_entities, \
    setup_chariot


@pytest.mark.cli
class TestZCli:

    def setup_class(self):
        self.sdk = setup_chariot()

    def test_asset_cli(self):
        o = make_test_values(lambda: None)

        verify_cli(f'add asset -n {o.asset_name} -d {o.asset_dns}')

        verify_cli('list assets -p all', [o.asset_key])
        verify_cli(f'list assets -f "{o.asset_dns}"', [o.asset_key])
        verify_cli(f'list assets -p first -f "{o.asset_dns}"', [o.asset_key])
        verify_cli(f'list assets -p all -f "{o.asset_dns}"', [o.asset_key])
        verify_cli(f'list assets -d -f "{o.asset_dns}"', [o.asset_key, '"key"', '"data"'])

        verify_cli(f'list assets -f {epoch_micro()}')

        verify_cli(f'get asset "{o.asset_key}"', [o.asset_key, f'"status": "{Asset.ACTIVE.value}"'])
        verify_cli(f'get asset -d "{o.asset_key}"', ['"attributes"', '"associated_risks"'])

        verify_cli(f'update asset -p discover "{o.asset_key}"')
        verify_cli(f'get asset "{o.asset_key}"', [o.asset_key, f'"status": "{Asset.ACTIVE_LOW.value}"'])

        verify_cli(f'delete asset "{o.asset_key}"')
        verify_cli(f'get asset "{o.asset_key}"', [f'"status": "{Asset.DELETED.value}"'])

        clean_test_entities(self.sdk, o)

    def test_risk_cli(self):
        o = make_test_values(lambda: None)
        verify_cli(f'add asset -n {o.asset_name} -d {o.asset_dns}')

        verify_cli(f'add risk {o.risk_name} -a "{o.asset_key}" -s {AddRisk.TRIAGE_HIGH.value}')

        verify_cli('list risks -p all', [o.risk_key])
        verify_cli(f'list risks -f "{o.asset_dns}"', [o.risk_key])
        verify_cli(f'list risks -d -f "{o.asset_dns}"', [o.risk_key, '"key"', '"data"'])
        verify_cli(f'list risks -f {epoch_micro()}')

        verify_cli(f'get risk "{o.risk_key}"', [o.risk_key, f'"status": "{AddRisk.TRIAGE_HIGH.value}"'])
        verify_cli(f'get risk -d "{o.risk_key}"', ['"attributes"', '"affected_assets"'])

        verify_cli(f'update risk "{o.risk_key}" -s {Risk.OPEN_LOW.value}')
        verify_cli(f'get risk "{o.risk_key}"', [o.risk_key, f'"status": "{Risk.OPEN_LOW.value}"'])

        verify_cli(f'delete risk "{o.risk_key}"')
        verify_cli(f'get risk "{o.risk_key}"', [f'"status": "{Risk.DELETED_LOW.value}"'])

        clean_test_entities(self.sdk, o)

    def test_definition_cli(self):
        definition_name = f'test-definition-{epoch_micro()}'
        local_filepath = f'{definition_name}.md'
        content = random_ip()

        with open(local_filepath, 'w') as f:
            f.write(content)

        verify_cli(f'add definition {local_filepath} -n {definition_name}')
        verify_cli(f'list definitions -f {definition_name}', [definition_name])
        verify_cli(f'list definitions -f {definition_name} -p all', [definition_name])
        verify_cli(f'list definitions -f {definition_name} -p first', [definition_name])
        verify_cli(f'get definition {definition_name}', ['Saved', definition_name])

        with open(definition_name, 'r') as f:
            assert f.read() == content

        os.remove(local_filepath)
        os.remove(definition_name)

    def test_attribute_cli(self):
        o = make_test_values(lambda: None)
        verify_cli(f'add asset -n {o.asset_name} -d {o.asset_dns}')
        verify_cli(f'add attribute -n {o.attribute_name} -v {o.attribute_value} -k "{o.asset_key}"')

        verify_cli('list attributes -p all', [o.asset_attribute_key])
        verify_cli(f'list attributes -f {o.attribute_name} -p all', [o.asset_attribute_key])
        verify_cli(f'list attributes -k "{o.asset_key}" -p all', [o.asset_attribute_key])
        verify_cli(f'list attributes -k "{o.asset_key}" -d -p all', [o.asset_attribute_key, '"key"', '"data"'])

        verify_cli(f'get attribute "{o.asset_attribute_key}"', [o.asset_attribute_key, '"key"', '"name"'])

        verify_cli(f'delete attribute "{o.asset_attribute_key}"')
        verify_cli(f'get attribute "{o.asset_attribute_key}"')

        clean_test_entities(self.sdk, o)

    def test_search_cli(self):
        o = make_test_values(lambda: None)
        verify_cli(f'add asset -n {o.asset_name} -d {o.asset_dns}')

        verify_cli(f'search -t "#asset#{o.asset_dns}"', [o.asset_key])
        verify_cli(f'search -t "#asset#{o.asset_dns}" -d', [o.asset_key, '"key"', '"data"'])
        verify_cli(f'search -t "#asset#{o.asset_dns}" -c', ['"A": 1'])

        verify_cli(f'search -t "source:{o.asset_key}"', ['surface#provided', o.asset_key, 'attribute'])
        verify_cli(f'search -t "ip:{o.asset_name}"', [o.asset_key])
        verify_cli(f'search -t "name:{o.asset_name}"', [o.asset_key])
        verify_cli(f'search -t "dns:{o.asset_dns}"', [o.asset_key])

        verify_cli(f'search -t "source:{o.asset_key}"', ['surface#provided', o.asset_key, 'attribute'])
        verify_cli(f'search -t "ip:{o.asset_name}"', [o.asset_key])
        verify_cli(f'search -t "name:{o.asset_name}"', [o.asset_key])
        verify_cli(f'search -t "dns:{o.asset_dns}"', [o.asset_key])
        verify_cli(f'search -t "status:{Asset.ACTIVE.value}"', [o.asset_key])

        verify_cli(f'add attribute -n {o.attribute_name} -v {o.attribute_value} -k "{o.asset_key}"')

        verify_cli(f'search -t "name:{o.attribute_name}"', [o.asset_key, 'attribute'])

        clean_test_entities(self.sdk, o)

    def test_webhook_cli(self):
        verify_cli(f'delete webhook', ignore_stdout=True)

        verify_cli(f'add webhook', ['amazonaws.com/', '/hook/', 'https://'])
        verify_cli(f'get webhook', ['amazonaws.com/', '/hook/', 'https://'])
        verify_cli(f'add webhook', ['There is an existing webhook.'])
        verify_cli(f'delete webhook', ['Webhook successfully deleted.'])
        verify_cli(f'delete webhook', ['No webhook previously exists.'])

    def test_account_cli(self):
        o = make_test_values(lambda: None)

        verify_cli(f'link account {o.email}')
        verify_cli(f'list accounts', [o.email])
        verify_cli(f'list accounts -d', [o.email, '"key"'])
        verify_cli(f'list accounts -f {o.email}', [o.email])
        verify_cli(f'unlink account {o.email}')
        verify_cli(f'list accounts -f {o.email}')

    def test_integration_cli(self):
        verify_cli('list integrations', ignore_stdout=True)
        verify_cli('list integrations -d', ignore_stdout=True)

    def test_help_cli(self):
        verify_cli('--help', ignore_stdout=True)
        verify_cli('list --help', ignore_stdout=True)
        verify_cli('list assets --help', ignore_stdout=True)
        verify_cli('list risks --help', ignore_stdout=True)
        verify_cli('list accounts --help', ignore_stdout=True)
        verify_cli('list integrations --help', ignore_stdout=True)
        verify_cli('list jobs --help', ignore_stdout=True)
        verify_cli('list files --help', ignore_stdout=True)
        verify_cli('list definitions --help', ignore_stdout=True)
        verify_cli('list attributes --help', ignore_stdout=True)

        verify_cli('get --help', ignore_stdout=True)
        verify_cli('get asset --help', ignore_stdout=True)
        verify_cli('get risk --help', ignore_stdout=True)
        verify_cli('get account --help', ignore_stdout=True)
        verify_cli('get integration --help', ignore_stdout=True)
        verify_cli('get job --help', ignore_stdout=True)
        verify_cli('get file --help', ignore_stdout=True)
        verify_cli('get definition --help', ignore_stdout=True)
        verify_cli('get attribute --help', ignore_stdout=True)
        verify_cli('get webhook --help', ignore_stdout=True)

        verify_cli('add --help', ignore_stdout=True)
        verify_cli('add asset --help', ignore_stdout=True)
        verify_cli('add risk --help', ignore_stdout=True)
        verify_cli('add attribute --help', ignore_stdout=True)
        verify_cli('add job --help', ignore_stdout=True)
        verify_cli('add file --help', ignore_stdout=True)
        verify_cli('add definition --help', ignore_stdout=True)
        verify_cli('add webhook --help', ignore_stdout=True)

        verify_cli('imports --help', ignore_stdout=True)
        verify_cli('imports qualys --help', ignore_stdout=True)
        verify_cli('imports insightvm --help', ignore_stdout=True)
        verify_cli('imports nessus --help', ignore_stdout=True)

        verify_cli('link --help', ignore_stdout=True)
        verify_cli('link account --help', ignore_stdout=True)

        verify_cli('unlink --help', ignore_stdout=True)
        verify_cli('unlink account --help', ignore_stdout=True)

        verify_cli('delete --help', ignore_stdout=True)
        verify_cli('delete asset --help', ignore_stdout=True)
        verify_cli('delete risk --help', ignore_stdout=True)
        verify_cli('delete attribute --help', ignore_stdout=True)
        verify_cli('delete webhook --help', ignore_stdout=True)

        verify_cli('update --help', ignore_stdout=True)
        verify_cli('update asset --help', ignore_stdout=True)
        verify_cli('update risk --help', ignore_stdout=True)

        verify_cli('search --help', ignore_stdout=True)
        verify_cli('script --help', ignore_stdout=True)
        verify_cli('purge --help', ignore_stdout=True)
