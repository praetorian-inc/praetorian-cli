import json
import types
import pytest
from praetorian_cli.ui.console.commands.marcus import MarcusCommands


class _Host(MarcusCommands):
    """Bare host exposing MarcusCommands methods for unit testing."""
    def __init__(self):
        pass


@pytest.fixture
def host():
    return _Host()


def test_parse_tool_name_from_structured_content(host):
    content = json.dumps({'name': 'run_capability', 'input': {'capability': 'nuclei'}})
    assert host._parse_tool_name(content, {}) == 'run_capability(nuclei)'

def test_parse_tool_name_falls_back_to_tool(host):
    assert host._parse_tool_name('not json', {}) == 'tool'

def test_parse_tool_result_counts_list(host):
    content = json.dumps({'assets': [1, 2, 3]})
    assert host._parse_tool_result(content) == '3 assets'

def test_infer_tool_from_response_status(host):
    assert host._infer_tool_from_response(json.dumps({'status': 'JF'})) == 'status_check'


class _FakeResp:
    def __init__(self, status, body='', payload=None, ok=None):
        self.status_code = status
        self.text = body
        self._payload = payload if payload is not None else {}
        self.ok = ok if ok is not None else (200 <= status < 300)
    def json(self):
        return self._payload


def _make_host_for_post(first_resp, second_resp=None, login='analyst@praetorian.com'):
    host = _Host()
    calls = {'n': 0}
    class _KC: account = 'client@acme.com'
    class _Accounts:
        def login_principal(self): return login
    class _SDK:
        keychain = _KC()
        accounts = _Accounts()
        def url(self, p): return 'https://x' + p
        def chariot_request(self, method, url, json=None):
            calls['n'] += 1
            if calls['n'] == 1:
                if isinstance(first_resp, Exception):
                    raise first_resp
                return first_resp
            return second_resp
    host.sdk = _SDK()
    host.context = types.SimpleNamespace(account='client@acme.com', mode='agent',
                                         conversation_id=None)
    class _Console:
        def print(self, *a, **k): pass
        def status(self, *a, **k):
            import contextlib
            return contextlib.nullcontext()
    host.console = _Console()
    host.colors = {'primary': 'red'}
    return host, calls


def test_impersonation_restored_after_exception(host):
    h, calls = _make_host_for_post(RuntimeError('boom'))
    with pytest.raises(RuntimeError):
        h._post_to_planner('hello')
    assert h.sdk.keychain.account == 'client@acme.com'
