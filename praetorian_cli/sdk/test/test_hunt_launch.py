from io import StringIO

from rich.console import Console

from praetorian_cli.ui.hunt_defaults import DEFAULT_FINISH_CRITERIA
from praetorian_cli.ui.hunt_launch import (
    HuntLaunchConfigurator,
    configure_hunt_launch,
)


def _config():
    return {
        'prompt': 'Assess internal services',
        'aggressiveness': 'balanced',
        'guardrails': '',
        'finish_criteria': DEFAULT_FINISH_CRITERIA,
        'expires': 24,
        'custom_tag': '',
        'model_tier': None,
    }


def test_launch_configurator_cycles_described_choices():
    configurator = HuntLaunchConfigurator(
        _config(),
        ['#asset#internal#10.0.0.5'],
        'aegis-one (endpoint-1, online)',
    )
    configurator.cursor = 5

    assert configurator.field[0] == 'aggressiveness'
    assert 'Default posture' in configurator.description()

    configurator.cycle(1)

    assert configurator.config['aggressiveness'] == 'aggressive'
    assert 'multi-hop pivots' in configurator.description()


def test_launch_configurator_edits_guardrails_and_validates_mandate():
    configurator = HuntLaunchConfigurator(_config(), [], 'endpoint-1')
    configurator.cursor = 6
    configurator.activate()
    configurator.clear_edit()
    configurator.append_edit('Do not test authentication')
    configurator.save_edit()

    assert configurator.config['guardrails'] == 'Do not test authentication'

    configurator.cursor = 0
    configurator.activate()
    configurator.clear_edit()
    configurator.save_edit()

    assert configurator.editing is True
    assert 'cannot be empty' in configurator.status


def test_launch_configurator_selects_one_credential_per_type():
    credentials = [
        {
            'credentialId': 'ad-1',
            'type': 'active-directory',
            'name': 'Corp AD',
            'domain': 'corp.example',
        },
        {
            'credentialId': 'web-1',
            'type': 'web-auth',
            'name': 'Internal portal',
            'accountKey': '#webapplication#https://internal.example/',
        },
    ]
    configurator = HuntLaunchConfigurator(
        _config(),
        [],
        'endpoint-1',
        credentials,
    )

    configurator.cursor = 3
    configurator.cycle(1)
    configurator.cursor = 4
    configurator.cycle(1)

    assert configurator.value('ad_credential') == 'Corp AD'
    assert configurator.value('web_auth_credential') == 'Internal portal'
    assert configurator.confirmed_config()['credential_ids'] == [
        'ad-1',
        'web-1',
    ]


def test_launch_configurator_reviews_targets_and_endpoint():
    configurator = HuntLaunchConfigurator(
        _config(),
        ['#asset#one#10.0.0.1', '#asset#two#10.0.0.2'],
        'aegis-one (endpoint-1, online)',
    )

    configurator.cursor = 1
    assert configurator.value('targets') == '2 selected'
    assert '#asset#one#10.0.0.1' in configurator.description()

    configurator.cursor = 2
    assert configurator.value('endpoint') == 'aegis-one (endpoint-1, online)'


def test_launch_wizard_preserves_non_tty_command_behavior():
    config = _config()

    result, used_wizard = configure_hunt_launch(
        Console(file=StringIO()),
        config,
        [],
        'endpoint-1',
    )

    assert used_wizard is False
    assert result == config
