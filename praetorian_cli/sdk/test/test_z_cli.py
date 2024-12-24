import os
from subprocess import run

import pytest

from praetorian_cli.sdk.model.globals import AddRisk, Asset, Risk, Seed, Attribute
from praetorian_cli.sdk.model.utils import seed_status
from praetorian_cli.sdk.test.utils import epoch_micro, random_ip, make_test_values, clean_test_entities, setup_chariot


@pytest.mark.cli
class TestZCli:

    def setup_class(self):
        self.sdk = setup_chariot()

    def test_asset_cli(self):
        o = make_test_values(lambda: None)

        self.verify(f'add asset -n {o.asset_name} -d {o.asset_dns}')

        self.verify('list assets -p all', [o.asset_key])
        self.verify(f'list assets -f "{o.asset_dns}"', [o.asset_key])
        self.verify(f'list assets -f "{o.asset_dns}" -p first', [o.asset_key])
        self.verify(f'list assets -f "{o.asset_dns}" -p all', [o.asset_key])
        self.verify(f'list assets -f "{o.asset_dns}" -d', [o.asset_key, '"key"', '"data"'])

        self.verify(f'list assets -f {epoch_micro()}')

        self.verify(f'get asset "{o.asset_key}"', [o.asset_key, f'"status": "{Asset.ACTIVE.value}"'])
        self.verify(f'get asset -d "{o.asset_key}"', ['"attributes"', '"associated_risks"'])

        self.verify(f'update asset -p discover "{o.asset_key}"')
        self.verify(f'get asset "{o.asset_key}"', [o.asset_key, f'"status": "{Asset.ACTIVE_LOW.value}"'])

        self.verify(f'delete asset "{o.asset_key}"')
        self.verify(f'get asset "{o.asset_key}"', [f'"status": "{Asset.DELETED.value}"'])

        clean_test_entities(self.sdk, o)

    def test_seed_cli(self):
        o = make_test_values(lambda: None)

        self.verify(f'add seed -d {o.seed_dns}')

        self.verify('list seeds -p all', [o.seed_key])
        self.verify('list seeds -t domain -p all', [o.seed_key])
        self.verify(f'list seeds -t domain -f "{o.seed_dns}"', [o.seed_key])
        self.verify(f'list seeds -t domain -f "{o.seed_dns}" -p first', [o.seed_key])
        self.verify(f'list seeds -t domain -f "{o.seed_dns}" -p all', [o.seed_key])
        self.verify(f'list seeds -t domain -f "{o.seed_dns}" -p first', [o.seed_key])
        self.verify(f'list seeds -t domain -f "{o.seed_dns}" -d', [o.seed_dns, '"key"', '"data"'])
        self.verify(f'list seeds -t ip -f "{o.seed_dns}"')
        self.verify(f'list seeds -f "{o.seed_dns}"', [],
                    ["When the DNS filter is specified, you also need to specify the type of the filter"])

        self.verify(f'list seeds -t domain -f {epoch_micro()}')

        self.verify(f'get seed "{o.seed_key}"',
                    [o.seed_key, f'"status": "{seed_status("domain", Seed.PENDING.value)}"'])
        self.verify(f'get seed -d "{o.seed_key}"', ['"attributes"'])

        self.verify(f'update seed -s {Seed.FROZEN.value} "{o.seed_key}"')
        self.verify(f'get seed "{o.seed_key}"',
                    [o.seed_key, f'"status": "{seed_status("domain", Seed.FROZEN.value)}"'])

        self.verify(f'delete seed "{o.seed_key}"')
        self.verify(f'get seed "{o.seed_key}"', [f'"status": "{seed_status("domain", Seed.DELETED.value)}"'])

        clean_test_entities(self.sdk, o)

    def test_risk_cli(self):
        o = make_test_values(lambda: None)
        self.verify(f'add asset -n {o.asset_name} -d {o.asset_dns}')

        self.verify(f'add risk {o.risk_name} -a "{o.asset_key}" -s {AddRisk.TRIAGE_HIGH.value}')

        self.verify('list risks -p all', [o.risk_key])
        self.verify(f'list risks -f "{o.asset_dns}"', [o.risk_key])
        self.verify(f'list risks -f "{o.asset_dns}" -p first', [o.risk_key])
        self.verify(f'list risks -f "{o.asset_dns}" -p all', [o.risk_key])
        self.verify(f'list risks -f "{o.asset_dns}" -d', [o.risk_key, '"key"', '"data"'])
        self.verify(f'list risks -f {epoch_micro()}')

        self.verify(f'get risk "{o.risk_key}"', [o.risk_key, f'"status": "{AddRisk.TRIAGE_HIGH.value}"'])
        self.verify(f'get risk -d "{o.risk_key}"', ['"attributes"', '"affected_assets"'])

        self.verify(f'update risk "{o.risk_key}" -s {Risk.OPEN_LOW.value}')
        self.verify(f'get risk "{o.risk_key}"', [o.risk_key, f'"status": "{Risk.OPEN_LOW.value}"'])

        self.verify(f'delete risk "{o.risk_key}"')
        self.verify(f'get risk "{o.risk_key}"', [f'"status": "{Risk.DELETED_LOW.value}"'])

        clean_test_entities(self.sdk, o)

    def test_definition_cli(self):
        definition_name = f'test-definition-{epoch_micro()}'
        local_filepath = f'{definition_name}.md'
        content = random_ip()

        with open(local_filepath, 'w') as f:
            f.write(content)

        self.verify(f'add definition {local_filepath} -n {definition_name}')
        self.verify(f'list definitions -f {definition_name}', [definition_name])
        self.verify(f'list definitions -f {definition_name} -p first', [definition_name])
        self.verify(f'list definitions -f {definition_name} -p all', [definition_name])
        self.verify(f'get definition {definition_name}', ['Saved', definition_name])

        with open(definition_name, 'r') as f:
            assert f.read() == content

        os.remove(local_filepath)
        os.remove(definition_name)

    def test_attribute_cli(self):
        o = make_test_values(lambda: None)
        self.verify(f'add asset -n {o.asset_name} -d {o.asset_dns}')
        self.verify(f'add attribute -n {o.attribute_name} -v {o.attribute_value} -k "{o.asset_key}"')

        self.verify('list attributes -p all', [o.asset_attribute_key])
        self.verify(f'list attributes -f {o.attribute_name} -p all', [o.asset_attribute_key])
        self.verify(f'list attributes -k "{o.asset_key}" -p all', [o.asset_attribute_key])
        self.verify(f'list attributes -k "{o.asset_key}" -d -p all', [o.asset_attribute_key, '"key"', '"data"'])

        self.verify(f'get attribute "{o.asset_attribute_key}"', [o.asset_attribute_key, '"key"', '"name"'])

        self.verify(f'update attribute -s {Attribute.DELETED.value} "{o.asset_attribute_key}"')
        self.verify(f'get seed "{o.asset_attribute_key}"',
                    [o.asset_attribute_key, f'"status": "{Attribute.DELETED.value}"'])

        self.verify(f'delete attribute "{o.asset_attribute_key}"')
        self.verify(f'get attribute "{o.asset_attribute_key}"')

        clean_test_entities(self.sdk, o)

    def test_search_cli(self):
        o = make_test_values(lambda: None)
        self.verify(f'add asset -n {o.asset_name} -d {o.asset_dns}')

        self.verify(f'search -t "#asset#{o.asset_dns}" -p all', [o.asset_key])
        self.verify(f'search -t "#asset#{o.asset_dns}" -d -p all', [o.asset_key, '"key"', '"data"'])
        self.verify(f'search -t "#asset#{o.asset_dns}" -c -p all', ['"A": 1'])

        self.verify(f'search -t "source:{o.asset_key}" -p all', ['surface#provided', o.asset_key, 'attribute'])
        self.verify(f'search -t "ip:{o.asset_name}" -p all', [o.asset_key])
        self.verify(f'search -t "name:{o.asset_name}" -p all', [o.asset_key])
        self.verify(f'search -t "dns:{o.asset_dns}" -p all', [o.asset_key])

        self.verify(f'search -t "source:{o.asset_key}" -p all', ['surface#provided', o.asset_key, 'attribute'])
        self.verify(f'search -t "ip:{o.asset_name}" -p all', [o.asset_key])
        self.verify(f'search -t "name:{o.asset_name}" -p all', [o.asset_key])
        self.verify(f'search -t "dns:{o.asset_dns}" -p all', [o.asset_key])
        self.verify(f'search -t "status:{Asset.ACTIVE.value}" -p all', [o.asset_key])

        self.verify(f'add attribute -n {o.attribute_name} -v {o.attribute_value} -k "{o.asset_key}"')

        self.verify(f'search -t "name:{o.attribute_name}" -p all', [o.asset_key, 'attribute'])

        clean_test_entities(self.sdk, o)

    def test_webhook_cli(self):
        self.verify(f'delete webhook', ignore_stdout=True)

        self.verify(f'add webhook', ['amazonaws.com/', '/hook/', 'https://'])
        self.verify(f'get webhook', ['amazonaws.com/', '/hook/', 'https://'])
        self.verify(f'add webhook', ['There is an existing webhook.'])
        self.verify(f'delete webhook', ['Webhook successfully deleted.'])
        self.verify(f'delete webhook', ['No webhook previously exists.'])

    def test_account_cli(self):
        o = make_test_values(lambda: None)

        self.verify(f'link account {o.email}')
        self.verify(f'list accounts', [o.email])
        self.verify(f'list accounts -d', [o.email, '"key"'])
        self.verify(f'list accounts -f {o.email}', [o.email])
        self.verify(f'unlink account {o.email}')
        self.verify(f'list accounts -f {o.email}')

    def test_integration_cli(self):
        self.verify('list integrations', ignore_stdout=True)
        self.verify('list integrations -d', ignore_stdout=True)

    def test_help_cli(self):
        self.verify('--help', ignore_stdout=True)
        self.verify('list --help', ignore_stdout=True)
        self.verify('list assets --help', ignore_stdout=True)
        self.verify('list risks --help', ignore_stdout=True)
        self.verify('list accounts --help', ignore_stdout=True)
        self.verify('list integrations --help', ignore_stdout=True)
        self.verify('list jobs --help', ignore_stdout=True)
        self.verify('list files --help', ignore_stdout=True)
        self.verify('list definitions --help', ignore_stdout=True)
        self.verify('list attributes --help', ignore_stdout=True)

        self.verify('get --help', ignore_stdout=True)
        self.verify('get asset --help', ignore_stdout=True)
        self.verify('get risk --help', ignore_stdout=True)
        self.verify('get account --help', ignore_stdout=True)
        self.verify('get integration --help', ignore_stdout=True)
        self.verify('get job --help', ignore_stdout=True)
        self.verify('get file --help', ignore_stdout=True)
        self.verify('get definition --help', ignore_stdout=True)
        self.verify('get attribute --help', ignore_stdout=True)
        self.verify('get webhook --help', ignore_stdout=True)

        self.verify('add --help', ignore_stdout=True)
        self.verify('add asset --help', ignore_stdout=True)
        self.verify('add risk --help', ignore_stdout=True)
        self.verify('add attribute --help', ignore_stdout=True)
        self.verify('add job --help', ignore_stdout=True)
        self.verify('add file --help', ignore_stdout=True)
        self.verify('add definition --help', ignore_stdout=True)
        self.verify('add webhook --help', ignore_stdout=True)

        self.verify('imports --help', ignore_stdout=True)
        self.verify('imports qualys --help', ignore_stdout=True)
        self.verify('imports insightvm --help', ignore_stdout=True)
        self.verify('imports nessus --help', ignore_stdout=True)

        self.verify('link --help', ignore_stdout=True)
        self.verify('link account --help', ignore_stdout=True)

        self.verify('unlink --help', ignore_stdout=True)
        self.verify('unlink account --help', ignore_stdout=True)

        self.verify('delete --help', ignore_stdout=True)
        self.verify('delete asset --help', ignore_stdout=True)
        self.verify('delete risk --help', ignore_stdout=True)
        self.verify('delete attribute --help', ignore_stdout=True)
        self.verify('delete webhook --help', ignore_stdout=True)

        self.verify('update --help', ignore_stdout=True)
        self.verify('update asset --help', ignore_stdout=True)
        self.verify('update risk --help', ignore_stdout=True)

        self.verify('search --help', ignore_stdout=True)
        self.verify('script --help', ignore_stdout=True)
        self.verify('purge --help', ignore_stdout=True)

    def verify(self, command, expected_stdout=[], expected_stderr=[], ignore_stdout=False):
        result = run(f'praetorian --profile "{self.sdk.keychain.profile}" chariot {command}', capture_output=True,
                     text=True, shell=True)
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
