import contextlib
import io
import sys
from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

import praetorian_cli.handlers.red_team  # noqa: F401
from praetorian_cli.handlers.chariot import chariot

OK = {'status': 'ok'}


def _mock_sdk():
    mock_sdk = MagicMock()
    mock_sdk.is_praetorian_user.return_value = True
    mock_sdk.red_team.deployment_launch.return_value = {'project_id': 'p1'}
    mock_sdk.red_team.deployment_delete.return_value = {'message': 'deleted'}
    mock_sdk.red_team.deployment_details.return_value = {'nodes': []}
    mock_sdk.red_team.deployment_history.return_value = [{'action': 'launch'}]
    mock_sdk.red_team.deployment_last_inputs.return_value = {'globals': {}}
    mock_sdk.red_team.deployment_node_schema.return_value = {'catalog': {}}
    mock_sdk.red_team.deployment_terraform.return_value = {'job_id': 'j1'}
    mock_sdk.red_team.deployment_collaborators.return_value = ['a@co.com']
    mock_sdk.red_team.deployment_tags.return_value = ['v1.0', 'v1.1']
    mock_sdk.red_team.campaign_create.return_value = OK
    mock_sdk.red_team.campaign_delete.return_value = OK
    mock_sdk.red_team.campaign_targets.return_value = [{'email': 'a@co.com'}]
    mock_sdk.red_team.campaign_authorize.return_value = {'status': 'live'}
    mock_sdk.red_team.campaign_funnel.return_value = {'sent': 10}
    mock_sdk.red_team.campaign_activity.return_value = [{'event': 'click'}]
    mock_sdk.red_team.domain_update.return_value = OK
    mock_sdk.red_team.dns_list.return_value = {'records': []}
    mock_sdk.red_team.dns_create.return_value = {'id': 'r1'}
    mock_sdk.red_team.dns_delete.return_value = OK
    mock_sdk.red_team.dns_update.return_value = OK
    mock_sdk.red_team.mailgun_domain_status.return_value = {'state': 'active'}
    mock_sdk.red_team.mailgun_domain_provision.return_value = OK
    mock_sdk.red_team.mailgun_domain_delete.return_value = OK
    mock_sdk.red_team.mailgun_user_create.return_value = {'username': 'u'}
    mock_sdk.red_team.mailgun_user_delete.return_value = OK
    mock_sdk.red_team.evilginx_phishlets.return_value = {'phishlets': []}
    mock_sdk.red_team.evilginx_phishlet_params.return_value = {'params': []}
    mock_sdk.red_team.evilginx_lures.return_value = {'lures': []}
    mock_sdk.red_team.evilginx_create_lure.return_value = {'job_id': 'j2'}
    mock_sdk.red_team.evilginx_configure.return_value = {'job_id': 'j3'}
    mock_sdk.red_team.evilginx_status.return_value = {'status': 'ready'}
    mock_sdk.red_team.payload_generate.return_value = {'job_id': 'j4'}
    mock_sdk.red_team.phishkit_nodes.return_value = [{'name': 'node-1'}]
    return mock_sdk


def _invoke(*args, stdin=None):
    runner = CliRunner()
    mock_sdk = _mock_sdk()
    with patch('praetorian_cli.sdk.chariot.Chariot', return_value=mock_sdk), \
         patch('praetorian_cli.handlers.cli_decorators.upgrade_check', lambda f: f):
        result = runner.invoke(
            chariot, list(args),
            obj={'keychain': MagicMock(), 'proxy': ''},
            input=stdin,
        )
    return result, mock_sdk


# --- Deployment ---

def test_deployment_launch():
    result, sdk = _invoke('red-team', 'deployment', 'launch')
    assert result.exit_code == 0
    sdk.red_team.deployment_launch.assert_called_once()


def test_deployment_launch_with_id():
    result, sdk = _invoke('red-team', 'deployment', 'launch', '--id', 'my-dep')
    assert result.exit_code == 0
    sdk.red_team.deployment_launch.assert_called_once_with(desired_id='my-dep')


def test_deployment_delete():
    result, sdk = _invoke('red-team', 'deployment', 'delete', '--yes')
    assert result.exit_code == 0
    sdk.red_team.deployment_delete.assert_called_once_with(force=False)


def test_deployment_details():
    result, sdk = _invoke('red-team', 'deployment', 'details')
    assert result.exit_code == 0
    sdk.red_team.deployment_details.assert_called_once()


def test_deployment_history():
    result, sdk = _invoke('red-team', 'deployment', 'history')
    assert result.exit_code == 0
    sdk.red_team.deployment_history.assert_called_once()


def test_deployment_last_inputs():
    result, sdk = _invoke('red-team', 'deployment', 'last-inputs')
    assert result.exit_code == 0
    sdk.red_team.deployment_last_inputs.assert_called_once()


def test_deployment_node_schema():
    result, sdk = _invoke('red-team', 'deployment', 'node-schema')
    assert result.exit_code == 0
    sdk.red_team.deployment_node_schema.assert_called_once_with(tag=None)


def test_deployment_node_schema_with_tag():
    result, sdk = _invoke('red-team', 'deployment', 'node-schema', '--tag', 'v1.0')
    assert result.exit_code == 0
    sdk.red_team.deployment_node_schema.assert_called_once_with(tag='v1.0')


def test_deployment_plan():
    body = '{"globals":{},"nodes":[]}'
    result, sdk = _invoke('red-team', 'deployment', 'plan', stdin=body)
    assert result.exit_code == 0
    sdk.red_team.deployment_terraform.assert_called_once()
    args = sdk.red_team.deployment_terraform.call_args
    assert args[0][0] == 'plan'


def test_deployment_apply():
    body = '{"globals":{},"nodes":[]}'
    result, sdk = _invoke('red-team', 'deployment', 'apply', '--yes', stdin=body)
    assert result.exit_code == 0
    sdk.red_team.deployment_terraform.assert_called_once()
    assert sdk.red_team.deployment_terraform.call_args[0][0] == 'apply'


def test_deployment_collaborators():
    result, sdk = _invoke(
        'red-team', 'deployment', 'collaborators',
        '--collaborators', 'a@co.com,b@co.com')
    assert result.exit_code == 0
    sdk.red_team.deployment_collaborators.assert_called_once_with(
        ['a@co.com', 'b@co.com'])


def test_deployment_tags():
    result, sdk = _invoke('red-team', 'deployment', 'tags')
    assert result.exit_code == 0
    sdk.red_team.deployment_tags.assert_called_once_with()


# --- Campaigns ---

def test_campaign_create():
    body = '{"name":"test","channel":"email"}'
    result, sdk = _invoke('red-team', 'campaign', 'create', stdin=body)
    assert result.exit_code == 0
    sdk.red_team.campaign_create.assert_called_once()


def test_campaign_delete():
    result, sdk = _invoke('red-team', 'campaign', 'delete', '--key', 'k1', '--yes')
    assert result.exit_code == 0
    sdk.red_team.campaign_delete.assert_called_once_with('k1')


def test_campaign_targets():
    body = '{"targets":[{"email":"a@co.com","name":"A"}]}'
    result, sdk = _invoke(
        'red-team', 'campaign', 'targets', '--id', 'c1', stdin=body)
    assert result.exit_code == 0
    sdk.red_team.campaign_targets.assert_called_once()


def test_campaign_authorize():
    result, sdk = _invoke('red-team', 'campaign', 'authorize', '--id', 'c1', '--yes')
    assert result.exit_code == 0
    sdk.red_team.campaign_authorize.assert_called_once_with('c1')


def test_campaign_funnel():
    result, sdk = _invoke('red-team', 'campaign', 'funnel', '--id', 'c1')
    assert result.exit_code == 0
    sdk.red_team.campaign_funnel.assert_called_once_with('c1')


def test_campaign_activity():
    result, sdk = _invoke('red-team', 'campaign', 'activity', '--id', 'c1')
    assert result.exit_code == 0
    sdk.red_team.campaign_activity.assert_called_once_with('c1', limit=None)


def test_campaign_activity_with_limit():
    result, sdk = _invoke(
        'red-team', 'campaign', 'activity', '--id', 'c1', '--limit', '25')
    assert result.exit_code == 0
    sdk.red_team.campaign_activity.assert_called_once_with('c1', limit=25)


# --- Domain parking ---

def test_domain_update():
    body = '{"domain":"evil.com","status":"in-use"}'
    result, sdk = _invoke('red-team', 'domain', 'update', stdin=body)
    assert result.exit_code == 0
    sdk.red_team.domain_update.assert_called_once()


def test_dns_list():
    result, sdk = _invoke('red-team', 'domain', 'dns-list', '--domain', 'evil.com')
    assert result.exit_code == 0
    sdk.red_team.dns_list.assert_called_once_with('evil.com')


def test_dns_create():
    result, sdk = _invoke(
        'red-team', 'domain', 'dns-create',
        '--domain', 'evil.com', '--type', 'A',
        '--name', 'www', '--content', '1.2.3.4')
    assert result.exit_code == 0
    sdk.red_team.dns_create.assert_called_once_with('evil.com', 'A', 'www', '1.2.3.4', 1)


def test_dns_update():
    result, sdk = _invoke(
        'red-team', 'domain', 'dns-update',
        '--domain', 'evil.com', '--record-id', 'r1', '--type', 'A',
        '--name', 'www', '--content', '1.2.3.4')
    assert result.exit_code == 0
    sdk.red_team.dns_update.assert_called_once_with(
        'evil.com', 'r1', 'A', 'www', '1.2.3.4', 1)


def test_dns_delete():
    result, sdk = _invoke(
        'red-team', 'domain', 'dns-delete',
        '--domain', 'evil.com', '--record-id', 'r1', '--yes')
    assert result.exit_code == 0
    sdk.red_team.dns_delete.assert_called_once_with('evil.com', 'r1')


def test_mailgun_status():
    result, sdk = _invoke(
        'red-team', 'domain', 'mailgun-status', '--domain', 'evil.com')
    assert result.exit_code == 0
    sdk.red_team.mailgun_domain_status.assert_called_once_with('evil.com')


def test_mailgun_provision():
    result, sdk = _invoke(
        'red-team', 'domain', 'mailgun-provision', '--domain', 'evil.com')
    assert result.exit_code == 0
    sdk.red_team.mailgun_domain_provision.assert_called_once_with('evil.com')


def test_mailgun_domain_delete():
    result, sdk = _invoke(
        'red-team', 'domain', 'mailgun-domain-delete', '--domain', 'evil.com', '--yes')
    assert result.exit_code == 0
    sdk.red_team.mailgun_domain_delete.assert_called_once_with('evil.com')


def test_mailgun_user():
    result, sdk = _invoke(
        'red-team', 'domain', 'mailgun-user',
        '--username', 'noreply', '--domain', 'evil.com')
    assert result.exit_code == 0
    sdk.red_team.mailgun_user_create.assert_called_once_with('noreply', 'evil.com')


def test_mailgun_user_delete():
    result, sdk = _invoke(
        'red-team', 'domain', 'mailgun-user-delete',
        '--username', 'noreply', '--domain', 'evil.com', '--yes')
    assert result.exit_code == 0
    sdk.red_team.mailgun_user_delete.assert_called_once_with('noreply', 'evil.com')


# --- Evilginx ---

def test_evilginx_phishlets():
    result, sdk = _invoke('red-team', 'evilginx', 'phishlets', '--node', 'n1')
    assert result.exit_code == 0
    sdk.red_team.evilginx_phishlets.assert_called_once_with('n1')


def test_evilginx_phishlet_params():
    result, sdk = _invoke(
        'red-team', 'evilginx', 'phishlet-params', '--node', 'n1', '--name', 'o365')
    assert result.exit_code == 0
    sdk.red_team.evilginx_phishlet_params.assert_called_once_with('n1', 'o365')


def test_evilginx_lures():
    result, sdk = _invoke('red-team', 'evilginx', 'lures', '--node', 'n1')
    assert result.exit_code == 0
    sdk.red_team.evilginx_lures.assert_called_once_with('n1')


def test_evilginx_create_lure():
    result, sdk = _invoke(
        'red-team', 'evilginx', 'create-lure', '--node', 'n1', '--path', '/login')
    assert result.exit_code == 0
    sdk.red_team.evilginx_create_lure.assert_called_once_with('n1', '/login')


def test_evilginx_configure():
    result, sdk = _invoke(
        'red-team', 'evilginx', 'configure',
        '--node', 'n1', '--domain', 'evil.com', '--phishlet', 'o365')
    assert result.exit_code == 0
    sdk.red_team.evilginx_configure.assert_called_once_with(
        'n1', 'evil.com', 'o365', phishlet_params=None, unauth_url=None)


def test_evilginx_configure_with_params():
    result, sdk = _invoke(
        'red-team', 'evilginx', 'configure',
        '--node', 'n1', '--domain', 'evil.com', '--phishlet', 'o365',
        '--params', '{"client_id":"abc"}')
    assert result.exit_code == 0
    sdk.red_team.evilginx_configure.assert_called_once_with(
        'n1', 'evil.com', 'o365',
        phishlet_params={'client_id': 'abc'}, unauth_url=None)


def test_evilginx_status():
    result, sdk = _invoke('red-team', 'evilginx', 'status', '--node', 'n1')
    assert result.exit_code == 0
    sdk.red_team.evilginx_status.assert_called_once_with('n1')


# --- Payload & phishkit ---

def test_payload_generate():
    result, sdk = _invoke(
        'red-team', 'payload-generate', '--shellcode', 'beacon.bin')
    assert result.exit_code == 0
    sdk.red_team.payload_generate.assert_called_once_with(
        'beacon.bin', variables=None)


def test_payload_generate_with_variables():
    result, sdk = _invoke(
        'red-team', 'payload-generate', '--shellcode', 'beacon.bin',
        '--variables', '{"dll_filename":"update.dll"}')
    assert result.exit_code == 0
    sdk.red_team.payload_generate.assert_called_once_with(
        'beacon.bin', variables={'dll_filename': 'update.dll'})


def test_phishkit_nodes():
    result, sdk = _invoke('red-team', 'phishkit-nodes')
    assert result.exit_code == 0
    sdk.red_team.phishkit_nodes.assert_called_once_with(status=None)


def test_phishkit_nodes_with_status():
    result, sdk = _invoke('red-team', 'phishkit-nodes', '--status', 'all')
    assert result.exit_code == 0
    sdk.red_team.phishkit_nodes.assert_called_once_with(status='all')


# --- Missing required args ---

def test_dns_create_missing_type():
    result, _ = _invoke(
        'red-team', 'domain', 'dns-create',
        '--domain', 'evil.com', '--name', 'www', '--content', '1.2.3.4')
    assert result.exit_code != 0


def test_evilginx_configure_missing_phishlet():
    result, _ = _invoke(
        'red-team', 'evilginx', 'configure', '--node', 'n1', '--domain', 'evil.com')
    assert result.exit_code != 0


def test_payload_generate_missing_shellcode():
    result, _ = _invoke('red-team', 'payload-generate')
    assert result.exit_code != 0


# --- stdin / JSON error handling ---

def test_load_json_body_tty_guard():
    import click

    from praetorian_cli.handlers.red_team import _load_json_body

    fake_stdin = MagicMock()
    fake_stdin.isatty.return_value = True
    with patch('praetorian_cli.handlers.red_team.sys.stdin', fake_stdin):
        try:
            _load_json_body()
            assert False, 'expected click.UsageError'
        except click.UsageError as e:
            assert 'Pipe JSON input via stdin' in str(e)


def test_read_json_body_invalid_json():
    result, sdk = _invoke('red-team', 'campaign', 'create', stdin='not valid json')
    assert result.exit_code != 0
    assert 'Invalid JSON input' in result.output
    sdk.red_team.campaign_create.assert_not_called()


def test_evilginx_configure_invalid_params_json():
    result, sdk = _invoke(
        'red-team', 'evilginx', 'configure',
        '--node', 'n1', '--domain', 'evil.com', '--phishlet', 'o365',
        '--params', 'not valid json')
    assert result.exit_code != 0
    assert 'Invalid JSON input' in result.output
    sdk.red_team.evilginx_configure.assert_not_called()


def test_payload_generate_invalid_variables_json():
    result, sdk = _invoke(
        'red-team', 'payload-generate', '--shellcode', 'beacon.bin',
        '--variables', 'not valid json')
    assert result.exit_code != 0
    assert 'Invalid JSON input' in result.output
    sdk.red_team.payload_generate.assert_not_called()


# --- Path segment validation (entity layer) ---

def test_segment_rejects_dot_segments():
    import pytest

    from praetorian_cli.sdk.entities.red_team import _segment

    for bad in ('..', '.', ''):
        with pytest.raises(ValueError, match='invalid URL path segment'):
            _segment(bad)


def test_segment_encodes_normal_values():
    from praetorian_cli.sdk.entities.red_team import _segment

    assert _segment('evil.com') == 'evil.com'
    assert _segment('a/b') == 'a%2Fb'
    assert _segment(7) == '7'


def _entity(is_praetorian=True):
    from praetorian_cli.sdk.entities.red_team import RedTeam

    api = MagicMock()
    api.is_praetorian_user.return_value = is_praetorian
    return RedTeam(api), api


def test_dns_delete_rejects_dot_segments_before_transmitting():
    import pytest

    rt, api = _entity()
    with pytest.raises(ValueError, match='invalid URL path segment'):
        rt.dns_delete('..', '..')
    api.delete.assert_not_called()


def test_campaign_activity_rejects_dot_segment():
    import pytest

    rt, api = _entity()
    with pytest.raises(ValueError, match='invalid URL path segment'):
        rt.campaign_activity('..')
    api.get.assert_not_called()


# --- SDK-layer Praetorian gating ---

def _required_arity(cls, name):
    import inspect

    sig = inspect.signature(getattr(cls, name))
    return len([p for p in sig.parameters.values()
                if p.name != 'self' and p.default is inspect.Parameter.empty])


def test_entity_methods_are_gated_for_non_praetorian_users():
    import pytest

    from praetorian_cli.sdk.entities.red_team import RedTeam

    rt, api = _entity(is_praetorian=False)
    public = [n for n in dir(RedTeam)
              if not n.startswith('_') and callable(getattr(RedTeam, n))]
    assert len(public) == 33
    for name in public:
        with pytest.raises(RuntimeError, match='limited to Praetorian engineers'):
            getattr(rt, name)(*(['x'] * _required_arity(RedTeam, name)))
    api.get.assert_not_called()
    api.post.assert_not_called()
    api.put.assert_not_called()
    api.delete.assert_not_called()


def test_red_team_is_a_sensitive_mcp_family():
    from praetorian_cli.sdk.mcp_server import (SENSITIVE_TOOL_PATTERNS,
                                               is_sensitive_tool)

    assert 'red_team_*' in SENSITIVE_TOOL_PATTERNS
    # Including the read-only members: they no longer ride a wildcard allow entry.
    assert is_sensitive_tool('red_team_dns_list')
    assert is_sensitive_tool('red_team_campaign_authorize')


# --- Terraform action constraint ---

def test_deployment_terraform_rejects_backend_only_actions():
    import pytest

    rt, api = _entity()
    for action in ('generate', 'outputs', 'tag'):
        with pytest.raises(ValueError, match='invalid terraform action'):
            rt.deployment_terraform(action, {})
    api.post.assert_not_called()


def test_deployment_terraform_allows_plan_and_apply():
    rt, api = _entity()
    rt.deployment_terraform('plan', {'nodes': []})
    rt.deployment_terraform('apply', {'nodes': []})
    assert [c[0][0] for c in api.post.call_args_list] == [
        'red-team/deployment/terraform/plan',
        'red-team/deployment/terraform/apply',
    ]


# --- MCP schema source (docstrings) ---

def test_every_entity_method_has_a_docstring():
    from praetorian_cli.sdk.entities.red_team import RedTeam

    for name in dir(RedTeam):
        if name.startswith('_'):
            continue
        method = getattr(RedTeam, name)
        if callable(method):
            assert (method.__doc__ or '').strip(), f'{name} has no docstring'


def test_builder_state_is_advertised_as_a_dict():
    from praetorian_cli.sdk.entities.red_team import RedTeam

    assert ':type builder_state: dict' in RedTeam.deployment_terraform.__doc__


# --- Confirmation on destructive commands ---

def test_apply_prompts_and_aborts_without_yes():
    result, sdk = _invoke('red-team', 'deployment', 'apply',
                          '--file', 'unused.json', stdin='n\n')
    assert result.exit_code != 0
    assert 'Apply the Terraform deployment?' in result.output
    sdk.red_team.deployment_terraform.assert_not_called()


def test_apply_with_a_bare_piped_body_fails_closed():
    result, sdk = _invoke('red-team', 'deployment', 'apply', stdin='{"a": 1}')
    assert result.exit_code == 1
    assert 'Apply the Terraform deployment?' in result.output
    sdk.red_team.deployment_terraform.assert_not_called()


# Security: a payload cannot answer its own confirmation prompt. The prompt is an
# eager Click parameter callback, so it consumes the body's first line before the
# body is ever read, and Click accepts only y/yes/n/no -- a truthy-looking token
# is rejected and the command aborts. No JSON document can begin with a line that
# is exactly `y` or `yes`, so no real payload can self-confirm.
@pytest.mark.parametrize('body', [
    'true\n{"a": 1}',
    '1\n{"a": 1}',
    'on\n{"a": 1}',
])
def test_apply_payload_cannot_self_confirm_the_prompt(body):
    result, sdk = _invoke('red-team', 'deployment', 'apply', stdin=body)
    assert result.exit_code == 1
    sdk.red_team.deployment_terraform.assert_not_called()


def test_apply_accepts_an_explicit_y_line_before_the_piped_body():
    result, sdk = _invoke('red-team', 'deployment', 'apply', stdin='y\n{"a": 1}')
    assert result.exit_code == 0
    sdk.red_team.deployment_terraform.assert_called_once()
    assert sdk.red_team.deployment_terraform.call_args[0][1] == {'a': 1}


def test_apply_accepts_a_spelled_out_yes_line_before_the_piped_body():
    result, sdk = _invoke('red-team', 'deployment', 'apply', stdin='yes\n{"a": 1}')
    assert result.exit_code == 0
    sdk.red_team.deployment_terraform.assert_called_once()
    assert sdk.red_team.deployment_terraform.call_args[0][1] == {'a': 1}


def test_campaign_delete_aborts_without_yes():
    result, sdk = _invoke('red-team', 'campaign', 'delete', '--key', 'k1',
                          stdin='n\n')
    assert result.exit_code != 0
    assert 'Delete this campaign?' in result.output
    sdk.red_team.campaign_delete.assert_not_called()


def test_authorize_aborts_without_yes():
    result, sdk = _invoke('red-team', 'campaign', 'authorize', '--id', 'c1',
                          stdin='n\n')
    assert result.exit_code != 0
    assert 'sends live phishing email to real recipients' in result.output
    sdk.red_team.campaign_authorize.assert_not_called()


def test_dns_delete_aborts_without_yes():
    result, sdk = _invoke('red-team', 'domain', 'dns-delete',
                          '--domain', 'evil.com', '--record-id', 'r1',
                          stdin='n\n')
    assert result.exit_code != 0
    assert 'Delete this DNS record?' in result.output
    sdk.red_team.dns_delete.assert_not_called()


# --- JSON body from a file ---

def test_plan_reads_body_from_file(tmp_path):
    body_file = tmp_path / 'builder.json'
    body_file.write_text('{"globals":{},"nodes":[]}')
    result, sdk = _invoke('red-team', 'deployment', 'plan', '--file', str(body_file))
    assert result.exit_code == 0
    assert sdk.red_team.deployment_terraform.call_args[0][1] == {
        'globals': {}, 'nodes': []}


def test_apply_reads_body_from_file_and_prompts_on_stdin(tmp_path):
    body_file = tmp_path / 'builder.json'
    body_file.write_text('{"globals":{},"nodes":[]}')
    result, sdk = _invoke('red-team', 'deployment', 'apply',
                          '--file', str(body_file), stdin='y\n')
    assert result.exit_code == 0
    assert 'Apply the Terraform deployment?' in result.output
    assert sdk.red_team.deployment_terraform.call_args[0][0] == 'apply'
    assert sdk.red_team.deployment_terraform.call_args[0][1] == {
        'globals': {}, 'nodes': []}


def test_load_json_body_missing_file():
    result, sdk = _invoke('red-team', 'campaign', 'create',
                          '--file', '/nonexistent/builder.json')
    assert result.exit_code != 0
    assert 'Cannot read JSON body from' in result.output
    sdk.red_team.campaign_create.assert_not_called()


def test_file_dash_reads_stdin():
    result, sdk = _invoke('red-team', 'campaign', 'create', '--file', '-',
                          stdin='{"name":"test"}')
    assert result.exit_code == 0
    sdk.red_team.campaign_create.assert_called_once_with({'name': 'test'})


# --- Secret material off argv ---

def test_configure_reads_params_from_file(tmp_path):
    params_file = tmp_path / 'params.json'
    params_file.write_text('{"client_id":"abc"}')
    result, sdk = _invoke(
        'red-team', 'evilginx', 'configure', '--node', 'n1',
        '--domain', 'evil.com', '--phishlet', 'o365',
        '--params-file', str(params_file))
    assert result.exit_code == 0
    sdk.red_team.evilginx_configure.assert_called_once_with(
        'n1', 'evil.com', 'o365',
        phishlet_params={'client_id': 'abc'}, unauth_url=None)


def test_configure_params_and_params_file_are_mutually_exclusive():
    result, sdk = _invoke(
        'red-team', 'evilginx', 'configure', '--node', 'n1',
        '--domain', 'evil.com', '--phishlet', 'o365',
        '--params', '{"a":1}', '--params-file', 'params.json')
    assert result.exit_code != 0
    assert '--params and --params-file are mutually exclusive' in result.output
    sdk.red_team.evilginx_configure.assert_not_called()


def test_payload_generate_reads_variables_from_file(tmp_path):
    vars_file = tmp_path / 'vars.json'
    vars_file.write_text('{"dll_filename":"update.dll"}')
    result, sdk = _invoke(
        'red-team', 'payload-generate', '--shellcode', 'beacon.bin',
        '--variables-file', str(vars_file))
    assert result.exit_code == 0
    sdk.red_team.payload_generate.assert_called_once_with(
        'beacon.bin', variables={'dll_filename': 'update.dll'})


def test_payload_generate_variables_and_file_are_mutually_exclusive():
    result, sdk = _invoke(
        'red-team', 'payload-generate', '--shellcode', 'beacon.bin',
        '--variables', '{"a":1}', '--variables-file', 'vars.json')
    assert result.exit_code != 0
    assert '--variables and --variables-file are mutually exclusive' in result.output
    sdk.red_team.payload_generate.assert_not_called()


# --- Input validation exit codes ---

def test_targets_bad_shape_is_a_usage_error():
    result, sdk = _invoke('red-team', 'campaign', 'targets', '--id', 'c1',
                          stdin='"just a string"')
    assert result.exit_code == 2
    assert "Expected JSON array or object with 'targets' key" in result.output
    sdk.red_team.campaign_targets.assert_not_called()


def test_targets_missing_key_is_a_usage_error():
    result, sdk = _invoke('red-team', 'campaign', 'targets', '--id', 'c1',
                          stdin='{"nope":[]}')
    assert result.exit_code == 2
    assert "Expected JSON with 'targets' key" in result.output
    sdk.red_team.campaign_targets.assert_not_called()


# --- Piped stdin is decoded as UTF-8 before anything reads it ---

# Real locale decoding is unreachable from a test: CliRunner's stdin is a BytesIO
# wrapper it decodes itself, and the process locale is fixed at interpreter start.
# What IS testable is the mechanism -- that the reconfigure happens at all, that a
# tty is left alone, and that it lands before the first read of the stream.
class _StdinStub:
    """A stdin that records reconfigure() and read calls, in order."""

    def __init__(self, payload='', tty=False, reconfigure_error=None):
        self._buffer = io.StringIO(payload)
        self._tty = tty
        self._reconfigure_error = reconfigure_error
        self.events = []
        self.reconfigure_calls = []

    def isatty(self):
        return self._tty

    def reconfigure(self, **kwargs):
        self.events.append('reconfigure')
        self.reconfigure_calls.append(kwargs)
        if self._reconfigure_error is not None:
            raise self._reconfigure_error

    def readline(self, *args):
        self.events.append('readline')
        return self._buffer.readline(*args)

    def read(self, *args):
        self.events.append('read')
        return self._buffer.read(*args)


def _invoke_with_stdin(stub, *args):
    """Drive the real CLI with `stub` installed as sys.stdin.

    CliRunner cannot carry a stub: isolation() overwrites sys.stdin with its own
    BytesIO wrapper, and hands the confirmation prompt that wrapper directly
    rather than going through sys.stdin -- so neither the reconfigure nor the
    prompt's read would land on the stub. main() leaves sys.stdin alone, and
    click's real prompt reads it through the builtin input().
    """
    mock_sdk = _mock_sdk()
    output = io.StringIO()
    with patch('praetorian_cli.sdk.chariot.Chariot', return_value=mock_sdk), \
         patch('praetorian_cli.handlers.cli_decorators.upgrade_check', lambda f: f), \
         patch.object(sys, 'stdin', stub), \
         contextlib.redirect_stdout(output), \
         contextlib.redirect_stderr(output):
        try:
            chariot.main(list(args), obj={'keychain': MagicMock(), 'proxy': ''},
                         standalone_mode=True)
            exit_code = 0
        except SystemExit as e:
            exit_code = e.code if e.code is not None else 0
    return exit_code, output.getvalue(), mock_sdk


def test_piped_stdin_is_reconfigured_to_utf8():
    # `details` takes no JSON body, so the group callback is the only thing that
    # can reconfigure here -- _load_json_body's own attempt never runs.
    stub = _StdinStub()
    exit_code, _, sdk = _invoke_with_stdin(stub, 'red-team', 'deployment', 'details')
    assert exit_code == 0
    assert stub.reconfigure_calls == [{'encoding': 'utf-8'}]
    sdk.red_team.deployment_details.assert_called_once()


def test_tty_stdin_is_not_reconfigured():
    # A tty never carries a JSON body, and its encoding is the terminal's.
    stub = _StdinStub(tty=True)
    exit_code, _, sdk = _invoke_with_stdin(stub, 'red-team', 'deployment', 'details')
    assert exit_code == 0
    assert stub.reconfigure_calls == [], stub.events
    sdk.red_team.deployment_details.assert_called_once()


def test_reconfigure_precedes_the_eager_confirmation_prompts_read():
    # The ordering IS the fix. reconfigure() is refused after the stream's first
    # read, and @click.confirmation_option is eager -- its prompt reads a line
    # before the command body runs. Anything that moves the call into a command
    # body arrives after this read and silently restores the locale decoder.
    stub = _StdinStub('y\n{"a": 1}')
    exit_code, output, sdk = _invoke_with_stdin(
        stub, 'red-team', 'deployment', 'apply')
    assert exit_code == 0
    assert 'Apply the Terraform deployment?' in output
    assert stub.events[0] == 'reconfigure', stub.events
    assert 'readline' in stub.events, stub.events
    assert sdk.red_team.deployment_terraform.call_args[0][1] == {'a': 1}


def test_a_stdin_without_reconfigure_is_tolerated():
    # sys.stdin is not always a TextIOWrapper; the helper must not raise.
    exit_code, _, sdk = _invoke_with_stdin(
        io.StringIO('{"name":"t"}'), 'red-team', 'campaign', 'create')
    assert exit_code == 0
    sdk.red_team.campaign_create.assert_called_once_with({'name': 't'})


def test_an_already_read_stdin_is_tolerated():
    # reconfigure() is refused once the stream has been read. The stream's own
    # decoder then stands and the command still runs.
    stub = _StdinStub('{"name":"t"}',
                      reconfigure_error=io.UnsupportedOperation('already read'))
    exit_code, _, sdk = _invoke_with_stdin(stub, 'red-team', 'campaign', 'create')
    assert exit_code == 0
    assert stub.reconfigure_calls, stub.events
    sdk.red_team.campaign_create.assert_called_once_with({'name': 't'})
