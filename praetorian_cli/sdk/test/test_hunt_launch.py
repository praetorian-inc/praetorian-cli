from io import StringIO

from rich.console import Console

from praetorian_cli.ui.hunt_defaults import (
    DEFAULT_EXTERNAL_MANDATE,
    DEFAULT_FINISH_CRITERIA,
    DEFAULT_HUNT_MANDATES,
)
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


def test_launch_configurator_explains_credential_availability():
    unavailable = HuntLaunchConfigurator(_config(), [], 'endpoint-1')
    unavailable.cursor = 3

    assert unavailable.value('ad_credential') == 'Unavailable'
    assert 'No active-directory credentials were returned' in (
        unavailable.description()
    )

    available = HuntLaunchConfigurator(
        _config(),
        [],
        'endpoint-1',
        [{
            'credentialId': 'ad-1',
            'type': 'active_directory',
            'name': 'Corp AD',
        }],
    )
    available.cursor = 3

    assert available.value('ad_credential') == 'None (1 available)'
    assert 'Press Left/Right, Space, or Enter' in available.description()
    available.activate()
    assert available.value('ad_credential') == 'Corp AD'


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


def _field_index(configurator, name):
    return next(
        index
        for index, (field_name, _label, _kind)
        in enumerate(configurator.fields)
        if field_name == name
    )


def test_all_surface_configurator_cycles_every_specific_surface_and_defaults():
    config = {
        **_config(),
        'surface': 'external',
        'scope_mode': 'specific',
        'prompt': DEFAULT_EXTERNAL_MANDATE,
    }
    configurator = HuntLaunchConfigurator(
        config,
        ['#asset#example.com#example.com'],
        'Not required',
    )
    configurator.cursor = _field_index(configurator, 'surface')

    for surface in ('internal', 'cloud', 'webapp', 'llm', 'external'):
        configurator.cycle(1)
        assert configurator.config['surface'] == surface
        assert configurator.config['prompt'] == DEFAULT_HUNT_MANDATES[surface]
        assert configurator.targets == []

    assert configurator.confirmed_config()['_resources_changed'] is True


def test_all_surface_configurator_preserves_custom_mandate_on_surface_change():
    configurator = HuntLaunchConfigurator(
        {
            **_config(),
            'surface': 'external',
            'scope_mode': 'specific',
            'prompt': 'Only assess the customer-approved objective',
        },
        ['#asset#example.com#example.com'],
        'Not required',
    )
    configurator.cursor = _field_index(configurator, 'surface')

    configurator.cycle(1)

    assert configurator.config['surface'] == 'internal'
    assert configurator.config['prompt'] == (
        'Only assess the customer-approved objective'
    )


def test_all_scope_mode_resets_surface_and_clears_specific_targets():
    configurator = HuntLaunchConfigurator(
        {
            **_config(),
            'surface': 'cloud',
            'scope_mode': 'specific',
            'prompt': DEFAULT_HUNT_MANDATES['cloud'],
        },
        ['#asset#aws#123456789012'],
        'Not required',
    )
    configurator.cursor = _field_index(configurator, 'scope_mode')

    configurator.cycle(-1)

    assert configurator.config['scope_mode'] == 'all'
    assert configurator.config['surface'] == 'external'
    assert configurator.config['prompt'] == DEFAULT_EXTERNAL_MANDATE
    assert configurator.value('targets') == 'All active targets'
    assert configurator.confirmed_config()['scope'] == []
