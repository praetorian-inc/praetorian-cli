from types import SimpleNamespace

from click.testing import CliRunner

from praetorian_cli.handlers.add import add
from praetorian_cli.handlers.get import get


class Search:
    def __init__(self, results):
        self.results = results

    def fulltext(self, _value, kind=None, limit=25):
        return list(self.results), None

    def by_term(self, _value, _kind, pages=1):
        return [], None


class Risks:
    def __init__(self):
        self.calls = []

    def add(self, *args):
        self.calls.append(args)


class Assets:
    def __init__(self):
        self.keys = []

    def get(self, key, details=False):
        self.keys.append((key, details))
        return {'key': key}


def test_add_risk_accepts_friendly_asset_reference():
    risks = Risks()
    sdk = SimpleNamespace(
        search=Search([{
            'key': '#asset#internal.example#10.0.0.5',
            'dns': 'internal.example',
            'identifier': '10.0.0.5',
        }]),
        risks=risks,
    )

    result = CliRunner().invoke(
        add,
        [
            'risk', 'smb-signing',
            '--asset', '10.0.0.5',
            '--status', 'TH',
        ],
        obj=sdk,
    )

    assert result.exit_code == 0, result.output
    assert risks.calls[0][0] == '#asset#internal.example#10.0.0.5'


def test_get_asset_fails_closed_for_ambiguous_noninteractive_reference():
    sdk = SimpleNamespace(
        search=Search([
            {'key': '#asset#one#10.0.0.5', 'name': 'shared'},
            {'key': '#asset#two#10.0.0.8', 'name': 'shared'},
        ]),
        assets=Assets(),
    )

    result = CliRunner().invoke(get, ['asset', 'shared'], obj=sdk)

    assert result.exit_code != 0
    assert 'matches multiple asset records' in result.output
    assert sdk.assets.keys == []
