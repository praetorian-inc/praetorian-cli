from types import SimpleNamespace

import pytest
from click.testing import CliRunner

from praetorian_cli.handlers.hunt import hunt
from praetorian_cli.sdk.model.aegis import Agent
from praetorian_cli.ui.hunt_defaults import (
    DEFAULT_EXTERNAL_MANDATE,
    DEFAULT_FINISH_CRITERIA,
    DEFAULT_HUNT_MANDATES,
)


ENDPOINT_ID = '11111111-1111-4111-8111-111111111111'
SURFACE_CASES = (
    (
        'external',
        ['--scope-mode', 'specific', '--scope', '#asset#example.com#example.com'],
        'hannibal',
        ['#asset#example.com#example.com'],
    ),
    (
        'internal',
        [
            '--internal',
            '--scope', '#asset#internal.example#10.0.0.5',
            '--endpoint', ENDPOINT_ID,
        ],
        'hannibal',
        ['#asset#internal.example#10.0.0.5'],
    ),
    (
        'cloud',
        ['--agent', 'hannibal-cloud', '--scope', '#asset#aws#123456789012'],
        'hannibal-cloud',
        ['#asset#aws#123456789012'],
    ),
    (
        'webapp',
        [
            '--agent', 'hannibal-webapp',
            '--scope', '#webapplication#https://portal.example/',
        ],
        'hannibal-webapp',
        ['#webapplication#https://portal.example/'],
    ),
    (
        'llm',
        [
            '--agent', 'hannibal-llm',
            '--scope', '#webapplication#https://assistant.example/',
        ],
        'hannibal-llm',
        ['#webapplication#https://assistant.example/'],
    ),
)


class FakeHunts:
    def __init__(self):
        self.create_calls = []

    def create(self, **kwargs):
        self.create_calls.append(kwargs)
        return {'uuid': 'hunt-1', **kwargs}


class FakeAssets:
    def __init__(self, candidates=None):
        self.candidates = list(candidates or [])
        self.calls = []

    def list_hunt_scope(self, **kwargs):
        self.calls.append(kwargs)
        return list(self.candidates), None


class FakeAegis:
    def __init__(self):
        self.endpoint = Agent.from_endpoint_dict({
            'endpointId': ENDPOINT_ID,
            'kind': 'aegis',
            'hostname': 'aegis-internal',
        })

    def list_hunt_endpoints(self):
        return [self.endpoint]


def _sdk(candidates=None):
    return SimpleNamespace(
        hunts=FakeHunts(),
        assets=FakeAssets(candidates),
        aegis=FakeAegis(),
    )


@pytest.mark.parametrize(
    'surface,args,expected_agent,expected_scope',
    SURFACE_CASES,
)
def test_yes_launch_sends_surface_default_and_complete_request_payload(
    surface,
    args,
    expected_agent,
    expected_scope,
):
    sdk = _sdk()

    result = CliRunner().invoke(
        hunt,
        [
            'launch',
            '--yes',
            *args,
            '--expires', '48',
            '--scope-level', 'strict',
            '--aggressiveness', 'aggressive',
            '--finish-criteria', 'Stop after one verified critical finding',
            '--guardrails', 'Do not test authentication',
            '--custom-tag', 'Q4-Hunt',
            '--model-tier', 'experimental',
        ],
        obj=sdk,
    )

    assert result.exit_code == 0, result.output
    assert sdk.hunts.create_calls == [{
        'prompt': DEFAULT_HUNT_MANDATES[surface],
        'expires_hours': 48,
        'agent': expected_agent,
        'scope': expected_scope,
        'scope_level': 'strict',
        'aggressiveness': 'aggressive',
        'finish_criteria': 'Stop after one verified critical finding',
        'user_guardrails': 'Do not test authentication',
        'custom_tag': 'Q4-Hunt',
        'model_tier_override': 'experimental',
        'credential_ids': None,
        'endpoint_required': surface == 'internal',
        'endpoint_id': ENDPOINT_ID if surface == 'internal' else None,
        'endpoint_confirmed': surface == 'internal',
    }]


@pytest.mark.parametrize(
    'surface,args,expected_agent,target',
    (
        (
            'external',
            [],
            'hannibal',
            '#asset#example.com#example.com',
        ),
        (
            'internal',
            ['--internal', '--endpoint', ENDPOINT_ID, '--confirm-endpoint'],
            'hannibal',
            '#asset#internal.example#10.0.0.5',
        ),
        (
            'cloud',
            ['--agent', 'hannibal-cloud'],
            'hannibal-cloud',
            '#asset#aws#123456789012',
        ),
        (
            'webapp',
            ['--agent', 'hannibal-webapp'],
            'hannibal-webapp',
            '#webapplication#https://portal.example/',
        ),
        (
            'llm',
            ['--agent', 'hannibal-llm'],
            'hannibal-llm',
            '#webapplication#https://assistant.example/',
        ),
    ),
)
def test_interactive_target_discovery_uses_selected_surface(
    monkeypatch,
    surface,
    args,
    expected_agent,
    target,
):
    sdk = _sdk([{'key': target, 'status': 'A'}])
    monkeypatch.setattr(
        'praetorian_cli.handlers.hunt.supports_fullscreen_wizard',
        lambda: True,
    )
    monkeypatch.setattr(
        'praetorian_cli.handlers.hunt.select_entity_keys',
        lambda _console, entities, **_kwargs: [entities[0]['key']],
    )
    monkeypatch.setattr(
        'praetorian_cli.handlers.hunt.configure_hunt_launch',
        lambda _console, config, *_args: (dict(config), True),
    )

    result = CliRunner().invoke(
        hunt,
        ['launch', *args, '--select-scope'],
        obj=sdk,
    )

    assert result.exit_code == 0, result.output
    assert sdk.assets.calls[0] == {
        'agent': expected_agent,
        'internal': surface == 'internal',
        'pages': 1,
    }
    assert sdk.hunts.create_calls[0]['scope'] == [target]


def test_all_scope_mode_uses_external_agent_and_omits_request_scope():
    sdk = _sdk()

    result = CliRunner().invoke(hunt, ['launch', '--yes'], obj=sdk)

    assert result.exit_code == 0, result.output
    payload = sdk.hunts.create_calls[0]
    assert payload['agent'] == 'hannibal'
    assert payload['prompt'] == DEFAULT_EXTERNAL_MANDATE
    assert payload['scope'] is None
    assert payload['finish_criteria'] == DEFAULT_FINISH_CRITERIA
    assert sdk.assets.calls == []


def test_existing_flags_initialize_wizard_and_wizard_surface_drives_payload(
    monkeypatch,
):
    sdk = _sdk()
    captured = {}

    monkeypatch.setattr(
        'praetorian_cli.handlers.hunt.supports_fullscreen_wizard',
        lambda: True,
    )

    def configure(_console, config, targets, endpoint, credentials):
        captured.update({
            'config': dict(config),
            'targets': list(targets),
            'endpoint': endpoint,
            'credentials': list(credentials),
        })
        return ({
            **config,
            'surface': 'cloud',
            'scope_mode': 'specific',
            'scope': ['#asset#aws#123456789012'],
        }, True)

    monkeypatch.setattr(
        'praetorian_cli.handlers.hunt.configure_hunt_launch',
        configure,
    )

    result = CliRunner().invoke(
        hunt,
        [
            'launch',
            '--prompt', 'Follow this custom mandate',
            '--expires', '48',
            '--aggressiveness', 'cautious',
            '--guardrails', 'Avoid login pages',
        ],
        obj=sdk,
    )

    assert result.exit_code == 0, result.output
    assert captured['config']['surface'] == 'external'
    assert captured['config']['scope_mode'] == 'all'
    assert captured['config']['prompt'] == 'Follow this custom mandate'
    assert captured['config']['expires'] == 48
    assert captured['config']['aggressiveness'] == 'cautious'
    assert captured['config']['guardrails'] == 'Avoid login pages'
    assert captured['targets'] == []
    assert sdk.hunts.create_calls[0]['agent'] == 'hannibal-cloud'
    assert sdk.hunts.create_calls[0]['scope'] == ['#asset#aws#123456789012']


def test_wizard_can_change_internal_specific_scope_to_external_all(monkeypatch):
    sdk = _sdk()
    monkeypatch.setattr(
        'praetorian_cli.handlers.hunt.supports_fullscreen_wizard',
        lambda: True,
    )

    def configure(_console, config, *_args):
        return ({
            **config,
            'surface': 'external',
            'scope_mode': 'all',
            'scope': [],
            'prompt': DEFAULT_EXTERNAL_MANDATE,
            'credential_ids': [],
        }, True)

    monkeypatch.setattr(
        'praetorian_cli.handlers.hunt.configure_hunt_launch',
        configure,
    )

    result = CliRunner().invoke(
        hunt,
        [
            'launch', '--internal',
            '--scope', '#asset#internal.example#10.0.0.5',
            '--endpoint', ENDPOINT_ID,
        ],
        obj=sdk,
    )

    assert result.exit_code == 0, result.output
    payload = sdk.hunts.create_calls[0]
    assert payload['agent'] == 'hannibal'
    assert payload['scope'] is None
    assert payload['endpoint_required'] is False
    assert payload['endpoint_id'] is None


def test_wizard_cancellation_creates_no_hunt(monkeypatch):
    sdk = _sdk()
    monkeypatch.setattr(
        'praetorian_cli.handlers.hunt.supports_fullscreen_wizard',
        lambda: True,
    )
    monkeypatch.setattr(
        'praetorian_cli.handlers.hunt.configure_hunt_launch',
        lambda *_args: (None, True),
    )

    result = CliRunner().invoke(hunt, ['launch'], obj=sdk)

    assert result.exit_code != 0
    assert 'Aborted' in result.output
    assert sdk.hunts.create_calls == []


def test_target_selection_cancellation_creates_no_hunt(monkeypatch):
    sdk = _sdk([{
        'key': '#asset#example.com#example.com',
        'status': 'A',
        'class': 'tld',
    }])
    monkeypatch.setattr(
        'praetorian_cli.handlers.hunt.supports_fullscreen_wizard',
        lambda: True,
    )
    monkeypatch.setattr(
        'praetorian_cli.handlers.hunt._select_hunt_scope',
        lambda *_args: [],
    )

    result = CliRunner().invoke(
        hunt,
        ['launch', '--select-scope'],
        obj=sdk,
    )

    assert result.exit_code != 0
    assert 'Aborted' in result.output
    assert sdk.hunts.create_calls == []


def test_yes_never_opens_wizard_or_target_selector(monkeypatch):
    sdk = _sdk()
    monkeypatch.setattr(
        'praetorian_cli.handlers.hunt.configure_hunt_launch',
        lambda *_args: pytest.fail('wizard must not run with --yes'),
    )
    monkeypatch.setattr(
        'praetorian_cli.handlers.hunt._select_hunt_scope',
        lambda *_args: pytest.fail('selector must not run with --yes'),
    )

    result = CliRunner().invoke(hunt, ['launch', '--yes'], obj=sdk)

    assert result.exit_code == 0, result.output
    assert len(sdk.hunts.create_calls) == 1


def test_non_tty_select_scope_fails_instead_of_opening_prompt_ui():
    sdk = _sdk()

    result = CliRunner().invoke(
        hunt,
        ['launch', '--select-scope'],
        obj=sdk,
        input='1\ndone\n',
    )

    assert result.exit_code != 0
    assert '--select-scope requires an interactive TTY' in result.output
    assert sdk.assets.calls == []
    assert sdk.hunts.create_calls == []


def test_non_tty_uses_defaults_without_prompting(monkeypatch):
    sdk = _sdk()
    captured = []
    monkeypatch.setattr(
        'praetorian_cli.handlers.hunt.supports_fullscreen_wizard',
        lambda: False,
    )

    def configure(_console, config, *_args):
        captured.append(dict(config))
        return dict(config), False

    monkeypatch.setattr(
        'praetorian_cli.handlers.hunt.configure_hunt_launch',
        configure,
    )

    result = CliRunner().invoke(hunt, ['launch'], obj=sdk, input='')

    assert result.exit_code == 0, result.output
    assert captured[0]['scope_mode'] == 'all'
    assert sdk.hunts.create_calls[0]['prompt'] == DEFAULT_EXTERNAL_MANDATE


@pytest.mark.parametrize(
    'args,message',
    (
        (
            ['--internal', '--scope', '#asset#internal#10.0.0.5'],
            '--endpoint is required',
        ),
        (
            ['--internal', '--endpoint', ENDPOINT_ID],
            'Specific Hunts require at least one --scope',
        ),
        (
            ['--agent', 'hannibal-cloud'],
            'Specific Hunts require at least one --scope',
        ),
    ),
)
def test_non_tty_incomplete_specific_launch_fails_without_prompt(args, message):
    sdk = _sdk()

    result = CliRunner().invoke(hunt, ['launch', *args], obj=sdk, input='')

    assert result.exit_code != 0
    assert message in result.output
    assert sdk.hunts.create_calls == []


def test_all_scope_rejects_surface_or_target_flags_deterministically():
    sdk = _sdk()

    result = CliRunner().invoke(
        hunt,
        [
            'launch', '--yes', '--scope-mode', 'all',
            '--agent', 'hannibal-webapp',
        ],
        obj=sdk,
    )

    assert result.exit_code != 0
    assert 'only valid for an unscoped External Hunt' in result.output
    assert sdk.hunts.create_calls == []
