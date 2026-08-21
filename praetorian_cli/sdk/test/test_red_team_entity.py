"""Unit tests for the RedTeam SDK entity layer.

test_red_team_cli.py exercises the CLI with sdk.red_team fully mocked, so it
never reaches the entity. These tests drive the entity directly against a
recording stub `api`, covering the `_segment` path-traversal guard, the
terraform action allowlist, and the URL/body/params each method builds.

The stub's method signatures mirror praetorian_cli/sdk/chariot.py:186-201
exactly (post/put/get/delete), so a call-shape drift in the entity surfaces
here as a TypeError rather than passing silently.
"""

import pytest

from praetorian_cli.sdk.entities.red_team import RedTeam, TERRAFORM_ACTIONS, _segment

SENTINEL = {'stub': 'response'}


class RecordingApi:
    """Stub `api` that records every call instead of performing it."""

    def __init__(self, is_praetorian=True):
        self.calls = []
        self._is_praetorian = is_praetorian

    def is_praetorian_user(self):
        return self._is_praetorian

    def post(self, type: str, body: dict, params: dict | None = None) -> dict:
        self.calls.append(('post', type, body, params))
        return SENTINEL

    def put(self, type: str, body: dict, params: dict | None = None) -> dict:
        self.calls.append(('put', type, body, params))
        return SENTINEL

    def get(self, type: str, params: dict | None = None) -> dict:
        self.calls.append(('get', type, params))
        return SENTINEL

    def delete(self, type: str, body: dict, params: dict) -> dict:
        self.calls.append(('delete', type, body, params))
        return SENTINEL


@pytest.fixture
def api():
    return RecordingApi()


@pytest.fixture
def red_team(api):
    return RedTeam(api)


# --------------------------------------------------------------------------
# _segment: the path-traversal guard
#
# Verified contract (praetorian_cli/sdk/entities/red_team.py:9-19): the guard
# REJECTS only the exact strings '', '.' and '..' after str() coercion. Every
# other value is ACCEPTED and percent-encoded with safe='', which is what
# defeats embedded traversal: '/' becomes '%2F', so the value can never split
# into extra path segments for `requests` to normalize away.
# --------------------------------------------------------------------------

@pytest.mark.parametrize('rejected', ['.', '..', ''])
def test_segment_rejects_dot_segments_and_empty(rejected):
    with pytest.raises(ValueError) as excinfo:
        _segment(rejected)
    assert str(excinfo.value) == f'invalid URL path segment: {rejected!r}'


def test_segment_encodes_embedded_traversal_rather_than_rejecting_it():
    result = _segment('a/../b')
    assert result == 'a%2F..%2Fb'
    # Anchored negative: the exact-equality above proves the anchor, so a
    # loosened guard that let a literal separator through changes both lines.
    assert '/' not in result


def test_segment_encodes_leading_separator_traversal():
    result = _segment('/..')
    assert result == '%2F..'
    assert '/' not in result


def test_segment_encodes_trailing_separator_traversal():
    result = _segment('../')
    assert result == '..%2F'
    assert '/' not in result


def test_segment_encodes_dot_with_trailing_separator():
    assert _segment('./') == '.%2F'


def test_segment_double_encodes_percent_encoded_traversal():
    # '..%2f' must not survive as a decodable separator downstream: the '%'
    # itself is encoded, so the server sees the literal text, not a slash.
    result = _segment('..%2f')
    assert result == '..%252f'
    assert '%2f' not in result.lower().replace('%252f', '')


def test_segment_double_encodes_percent_encoded_dots():
    assert _segment('%2e%2e') == '%252e%252e'


def test_segment_encodes_backslash_traversal():
    result = _segment('..\\')
    assert result == '..%5C'
    assert '\\' not in result


def test_segment_accepts_triple_dot_verbatim():
    # The guard is exact-match, not a dot-prefix check: '...' is not a
    # dot-segment and is a legal path component, so it passes through unchanged.
    assert _segment('...') == '...'


def test_segment_does_not_strip_whitespace_around_dot_segments():
    # ' .. ' is not the exact string '..', so it is accepted; the spaces are
    # encoded, which keeps it distinct from a real dot-segment on the wire.
    assert _segment(' .. ') == '%20..%20'


def test_segment_passes_ordinary_value_through_unchanged():
    assert _segment('campaign-1') == 'campaign-1'


def test_segment_percent_encodes_non_ascii():
    assert _segment('café') == 'caf%C3%A9'


def test_segment_percent_encodes_unicode_beyond_latin1():
    assert _segment('テスト') == '%E3%83%86%E3%82%B9%E3%83%88'


@pytest.mark.parametrize('raw,encoded', [
    ('a b', 'a%20b'),
    ('a#b', 'a%23b'),
    ('foo?bar=1', 'foo%3Fbar%3D1'),
    ('x/y', 'x%2Fy'),
    ('#campaign#my-camp', '%23campaign%23my-camp'),
])
def test_segment_percent_encodes_reserved_characters(raw, encoded):
    assert _segment(raw) == encoded


@pytest.mark.parametrize('value,expected', [
    (0, '0'),
    (1, '1'),
    (None, 'None'),
])
def test_segment_coerces_non_strings_before_validating(value, expected):
    # The emptiness check runs on str(value), not on value, so 0 and None are
    # accepted as their textual forms rather than rejected as falsy.
    assert _segment(value) == expected


# --------------------------------------------------------------------------
# deployment_terraform: the plan/apply allowlist
# --------------------------------------------------------------------------

def test_deployment_terraform_plan_posts_builder_state_to_plan_path(red_team, api):
    state = {'globals': {'region': 'us-east-1'}}
    assert red_team.deployment_terraform('plan', state) is SENTINEL
    assert api.calls == [
        ('post', 'red-team/deployment/terraform/plan', state, {}),
    ]


def test_deployment_terraform_apply_posts_builder_state_to_apply_path(red_team, api):
    state = {'nodes': [{'type': 'phishkit'}]}
    red_team.deployment_terraform('apply', state)
    assert api.calls == [
        ('post', 'red-team/deployment/terraform/apply', state, {}),
    ]


def test_deployment_terraform_passes_tag_and_sha_as_query_params(red_team, api):
    red_team.deployment_terraform('plan', {}, tag='v1.1', sha='abc123')
    assert api.calls == [
        ('post', 'red-team/deployment/terraform/plan', {},
         {'tag': 'v1.1', 'sha': 'abc123'}),
    ]


def test_deployment_terraform_omits_unset_tag_and_sha(red_team, api):
    red_team.deployment_terraform('apply', {}, tag=None, sha='')
    assert api.calls == [
        ('post', 'red-team/deployment/terraform/apply', {}, {}),
    ]


@pytest.mark.parametrize('backend_only', ['generate', 'outputs', 'tag'])
def test_deployment_terraform_refuses_backend_only_actions(red_team, api, backend_only):
    # Anchor the negative assertion: prove the recorder captures an accepted
    # call first, so "no second call" is evidence rather than a drifted no-op.
    red_team.deployment_terraform('plan', {})
    assert len(api.calls) == 1

    with pytest.raises(ValueError) as excinfo:
        red_team.deployment_terraform(backend_only, {'nodes': []})
    assert str(excinfo.value) == (
        f'invalid terraform action: {backend_only!r}; '
        f"expected one of 'plan', 'apply'"
    )
    assert len(api.calls) == 1


@pytest.mark.parametrize('hostile', ['..', '.', '', '../generate', 'PLAN', 'plan/apply'])
def test_deployment_terraform_refuses_actions_outside_the_allowlist(red_team, api, hostile):
    red_team.deployment_terraform('plan', {})
    assert len(api.calls) == 1

    with pytest.raises(ValueError):
        red_team.deployment_terraform(hostile, {})
    assert len(api.calls) == 1


def test_terraform_allowlist_error_enumerates_only_reachable_actions(red_team):
    with pytest.raises(ValueError) as excinfo:
        red_team.deployment_terraform('generate', {})
    message = str(excinfo.value)
    assert message.endswith("expected one of 'plan', 'apply'")
    for backend_only in ('generate', 'outputs'):
        assert f"'{backend_only}'" not in message.split('expected one of')[1]


def test_terraform_actions_constant_gates_exactly_plan_and_apply():
    # Not a constant-identity test: this pins the reachable surface, so adding
    # a backend-only sub-step to the tuple reddens here and in the CLI suite.
    assert TERRAFORM_ACTIONS == ('plan', 'apply')


# --------------------------------------------------------------------------
# URL / body / params construction
# --------------------------------------------------------------------------

def test_deployment_launch_posts_empty_body_when_no_id_requested(red_team, api):
    red_team.deployment_launch()
    assert api.calls == [('post', 'red-team/deployment/launch', {}, None)]


def test_deployment_launch_includes_requested_deployment_id(red_team, api):
    red_team.deployment_launch('my-dep')
    assert api.calls == [
        ('post', 'red-team/deployment/launch', {'desired_id': 'my-dep'}, None),
    ]


def test_deployment_delete_sends_force_param_as_string_true(red_team, api):
    red_team.deployment_delete(force=True)
    assert api.calls == [
        ('delete', 'red-team/deployment/delete', {}, {'force': 'true'}),
    ]


def test_deployment_delete_omits_force_param_by_default(red_team, api):
    red_team.deployment_delete()
    assert api.calls == [('delete', 'red-team/deployment/delete', {}, {})]


@pytest.mark.parametrize('method,path', [
    ('deployment_details', 'red-team/deployment/details'),
    ('deployment_history', 'red-team/deployment/history'),
    ('deployment_last_inputs', 'red-team/deployment/last-inputs'),
    ('deployment_tags', 'red-team/deployment/tags'),
])
def test_parameterless_deployment_reads_get_their_own_path(red_team, api, method, path):
    getattr(red_team, method)()
    assert api.calls == [('get', path, None)]


def test_deployment_node_schema_passes_tag_param(red_team, api):
    red_team.deployment_node_schema('v1.1')
    assert api.calls == [
        ('get', 'red-team/deployment/node-schema', {'tag': 'v1.1'}),
    ]


def test_deployment_node_schema_omits_tag_param_when_unset(red_team, api):
    red_team.deployment_node_schema()
    assert api.calls == [('get', 'red-team/deployment/node-schema', {})]


def test_deployment_collaborators_wraps_list_in_body(red_team, api):
    red_team.deployment_collaborators(['a@co.com', 'b@co.com'])
    assert api.calls == [
        ('post', 'red-team/deployment/collaborators',
         {'collaborators': ['a@co.com', 'b@co.com']}, None),
    ]


def test_campaign_create_puts_document_to_campaigns_collection(red_team, api):
    campaign = {'name': 'q3-phish', 'template': 'invoice'}
    red_team.campaign_create(campaign)
    assert api.calls == [('put', 'red-team/campaigns', campaign, None)]


def test_campaign_delete_sends_key_in_body_not_in_path(red_team, api):
    red_team.campaign_delete('#campaign#my-camp')
    assert api.calls == [
        ('delete', 'red-team/campaigns', {'key': '#campaign#my-camp'}, {}),
    ]


def test_campaign_authorize_quotes_the_campaign_id_in_the_path(red_team, api):
    red_team.campaign_authorize('camp/../admin')
    assert api.calls == [
        ('post', 'red-team/campaigns/camp%2F..%2Fadmin/authorize', {}, None),
    ]


def test_campaign_authorize_refuses_a_dot_segment_campaign_id(red_team, api):
    red_team.campaign_authorize('camp-1')
    assert len(api.calls) == 1

    with pytest.raises(ValueError):
        red_team.campaign_authorize('..')
    assert len(api.calls) == 1


def test_campaign_targets_builds_path_and_roster_body(red_team, api):
    targets = [{'email': 'a@co.com'}]
    red_team.campaign_targets('camp-1', targets)
    assert api.calls == [
        ('post', 'red-team/campaigns/camp-1/targets', {'targets': targets}, None),
    ]


def test_campaign_targets_includes_segment_when_supplied(red_team, api):
    targets = [{'email': 'a@co.com'}]
    red_team.campaign_targets('camp-1', targets, segment='finance')
    assert api.calls == [
        ('post', 'red-team/campaigns/camp-1/targets',
         {'targets': targets, 'segment': 'finance'}, None),
    ]


def test_campaign_funnel_gets_the_funnel_subpath(red_team, api):
    red_team.campaign_funnel('café-camp')
    assert api.calls == [('get', 'red-team/campaigns/caf%C3%A9-camp/funnel', None)]


def test_campaign_activity_stringifies_the_limit_param(red_team, api):
    red_team.campaign_activity('camp-1', limit=25)
    assert api.calls == [
        ('get', 'red-team/campaigns/camp-1/activity', {'limit': '25'}),
    ]


def test_campaign_activity_omits_limit_param_when_unset(red_team, api):
    red_team.campaign_activity('camp-1')
    assert api.calls == [('get', 'red-team/campaigns/camp-1/activity', {})]


def test_domain_update_puts_document_to_domain_parking(red_team, api):
    domain_data = {'domain': 'evil.example', 'engagement': 'e1'}
    red_team.domain_update(domain_data)
    assert api.calls == [('put', 'red-team/domain-parking', domain_data, None)]


def test_dns_list_quotes_the_domain_in_the_path(red_team, api):
    red_team.dns_list('evil.example')
    assert api.calls == [
        ('get', 'red-team/domain-parking/dns/evil.example', None),
    ]


def test_dns_create_posts_the_record_body(red_team, api):
    red_team.dns_create('evil.example', 'A', 'www', '10.0.0.1')
    assert api.calls == [
        ('post', 'red-team/domain-parking/dns/evil.example',
         {'type': 'A', 'name': 'www', 'content': '10.0.0.1', 'ttl': 1}, None),
    ]


def test_dns_update_puts_the_record_body_to_a_two_segment_path(red_team, api):
    red_team.dns_update('evil.example', 'rec-1', 'CNAME', 'mail',
                        'target.example', ttl=300)
    assert api.calls == [
        ('put', 'red-team/domain-parking/dns/evil.example/rec-1',
         {'type': 'CNAME', 'name': 'mail', 'content': 'target.example',
          'ttl': 300}, None),
    ]


def test_dns_delete_quotes_both_path_segments(red_team, api):
    red_team.dns_delete('evil.example', 'rec-1')
    assert api.calls == [
        ('delete', 'red-team/domain-parking/dns/evil.example/rec-1', {}, {}),
    ]


def test_dns_delete_encodes_traversal_in_both_segments(red_team, api):
    red_team.dns_delete('a/../b', 'x/../y')
    verb, path, body, params = api.calls[0]
    assert path == 'red-team/domain-parking/dns/a%2F..%2Fb/x%2F..%2Fy'
    # The literal path has exactly the four separators the route itself
    # contributes; neither caller value added one.
    assert path.count('/') == 4
    assert (verb, body, params) == ('delete', {}, {})


@pytest.mark.parametrize('domain,record_id', [
    ('..', 'rec-1'),
    ('.', 'rec-1'),
    ('evil.example', '..'),
    ('evil.example', ''),
])
def test_dns_delete_refuses_dot_segments_in_either_position(red_team, api,
                                                            domain, record_id):
    red_team.dns_delete('evil.example', 'rec-1')
    assert len(api.calls) == 1

    with pytest.raises(ValueError):
        red_team.dns_delete(domain, record_id)
    assert len(api.calls) == 1


def test_mailgun_domain_status_gets_the_mailgun_domain_path(red_team, api):
    red_team.mailgun_domain_status('evil.example')
    assert api.calls == [
        ('get', 'red-team/domain-parking/mailgun/domain/evil.example', None),
    ]


def test_mailgun_domain_provision_posts_an_empty_body(red_team, api):
    red_team.mailgun_domain_provision('evil.example')
    assert api.calls == [
        ('post', 'red-team/domain-parking/mailgun/domain/evil.example', {}, None),
    ]


def test_mailgun_domain_delete_sends_empty_body_and_params(red_team, api):
    red_team.mailgun_domain_delete('evil.example')
    assert api.calls == [
        ('delete', 'red-team/domain-parking/mailgun/domain/evil.example', {}, {}),
    ]


def test_mailgun_user_create_sends_username_and_domain_in_body(red_team, api):
    red_team.mailgun_user_create('phish', 'evil.example')
    assert api.calls == [
        ('post', 'red-team/domain-parking/mailgun/user',
         {'username': 'phish', 'domain': 'evil.example'}, None),
    ]


def test_mailgun_user_delete_sends_username_and_domain_in_body(red_team, api):
    red_team.mailgun_user_delete('phish', 'evil.example')
    assert api.calls == [
        ('delete', 'red-team/domain-parking/mailgun/user',
         {'username': 'phish', 'domain': 'evil.example'}, {}),
    ]


def test_evilginx_phishlets_passes_node_as_a_query_param(red_team, api):
    red_team.evilginx_phishlets('node-1')
    assert api.calls == [
        ('get', 'red-team/evilginx/phishlets', {'node': 'node-1'}),
    ]


def test_evilginx_phishlet_params_quotes_the_name_and_keeps_node_a_param(red_team, api):
    red_team.evilginx_phishlet_params('node-1', 'o365')
    assert api.calls == [
        ('get', 'red-team/evilginx/phishlets/o365/params', {'node': 'node-1'}),
    ]


def test_evilginx_phishlet_params_refuses_a_dot_segment_name(red_team, api):
    red_team.evilginx_phishlet_params('node-1', 'o365')
    assert len(api.calls) == 1

    with pytest.raises(ValueError):
        red_team.evilginx_phishlet_params('node-1', '..')
    assert len(api.calls) == 1


def test_evilginx_create_lure_posts_node_ref_and_path(red_team, api):
    red_team.evilginx_create_lure('node-1', '/login')
    assert api.calls == [
        ('post', 'red-team/evilginx/lures',
         {'node_ref': 'node-1', 'lure_path': '/login'}, None),
    ]


def test_evilginx_configure_posts_only_the_supplied_optional_fields(red_team, api):
    red_team.evilginx_configure('node-1', 'evil.example', 'o365')
    assert api.calls == [
        ('post', 'red-team/evilginx/configure',
         {'node_ref': 'node-1', 'domain': 'evil.example', 'phishlet': 'o365'},
         None),
    ]


def test_evilginx_configure_includes_phishlet_params_and_unauth_url(red_team, api):
    red_team.evilginx_configure('node-1', 'evil.example', 'o365',
                                phishlet_params={'tenant': 'acme'},
                                unauth_url='https://example.com')
    assert api.calls == [
        ('post', 'red-team/evilginx/configure',
         {'node_ref': 'node-1', 'domain': 'evil.example', 'phishlet': 'o365',
          'phishlet_params': {'tenant': 'acme'},
          'unauth_url': 'https://example.com'}, None),
    ]


def test_evilginx_configure_keeps_an_explicitly_empty_phishlet_params(red_team, api):
    # `is not None` rather than truthiness: {} must reach the backend as an
    # explicit "no parameters" rather than being dropped.
    red_team.evilginx_configure('node-1', 'evil.example', 'o365',
                                phishlet_params={})
    assert api.calls == [
        ('post', 'red-team/evilginx/configure',
         {'node_ref': 'node-1', 'domain': 'evil.example', 'phishlet': 'o365',
          'phishlet_params': {}}, None),
    ]


def test_payload_generate_maps_filename_to_the_s3_body_field(red_team, api):
    red_team.payload_generate('shell.bin')
    assert api.calls == [
        ('post', 'red-team/payload/generate',
         {'shellcode_s3_filename': 'shell.bin'}, None),
    ]


def test_payload_generate_keeps_an_explicitly_empty_variables_map(red_team, api):
    red_team.payload_generate('shell.bin', variables={})
    assert api.calls == [
        ('post', 'red-team/payload/generate',
         {'shellcode_s3_filename': 'shell.bin', 'variables': {}}, None),
    ]


def test_phishkit_nodes_passes_status_filter(red_team, api):
    red_team.phishkit_nodes('running')
    assert api.calls == [
        ('get', 'red-team/phishkit-nodes', {'status': 'running'}),
    ]


def test_phishkit_nodes_omits_status_filter_when_unset(red_team, api):
    red_team.phishkit_nodes()
    assert api.calls == [('get', 'red-team/phishkit-nodes', {})]


# --------------------------------------------------------------------------
# The Praetorian-only gate
# --------------------------------------------------------------------------

@pytest.mark.parametrize('method,args', [
    ('deployment_launch', ()),
    ('deployment_delete', ()),
    ('deployment_details', ()),
    ('deployment_terraform', ('apply', {})),
    ('campaign_authorize', ('camp-1',)),
    ('campaign_delete', ('#campaign#c',)),
    ('dns_delete', ('evil.example', 'rec-1')),
    ('mailgun_domain_delete', ('evil.example',)),
    ('payload_generate', ('shell.bin',)),
])
def test_non_praetorian_user_is_refused_before_any_api_call(method, args):
    # Anchor: the same call on a Praetorian api reaches the stub, so the
    # empty call list below is the gate firing, not an unexercised path.
    allowed = RecordingApi(is_praetorian=True)
    getattr(RedTeam(allowed), method)(*args)
    assert len(allowed.calls) == 1

    refused = RecordingApi(is_praetorian=False)
    with pytest.raises(RuntimeError) as excinfo:
        getattr(RedTeam(refused), method)(*args)
    assert 'limited to Praetorian engineers only' in str(excinfo.value)
    assert refused.calls == []
