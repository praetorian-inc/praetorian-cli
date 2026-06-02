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


def test_non_json_response_raises_marcus_error(host):
    from praetorian_cli.ui.console.commands.marcus import MarcusError
    bad = _FakeResp(500, body='<html>oops</html>')
    def _json(): raise ValueError('no json')
    bad.json = _json
    h, _ = _make_host_for_post(bad)
    with pytest.raises(MarcusError):
        h._post_to_planner('hi')

def test_403_retries_through_praetorian_account(host):
    first = _FakeResp(403, body='forbidden')
    second = _FakeResp(200, payload={'conversation': {'uuid': 'c1'}})
    h, calls = _make_host_for_post(first, second)
    out = h._post_to_planner('hi')
    assert calls['n'] == 2
    assert out['conversation']['uuid'] == 'c1'
    assert h.sdk.keychain.account == 'client@acme.com'  # restored


def test_poll_messages_yields_only_new_and_stops_on_chariot(host):
    msgs_round1 = [{'key': '#message#c1#001', 'role': 'tool call', 'content': '{}'},
                   {'key': '#message#c1#002', 'role': 'tool response', 'content': '{"assets":[1]}'}]
    msgs_round2 = msgs_round1 + [{'key': '#message#c1#003', 'role': 'chariot', 'content': 'final answer'}]
    rounds = iter([msgs_round1, msgs_round2])
    class _Search:
        def by_key_prefix(self, prefix, user=False):
            return (next(rounds), None)
    host.sdk = types.SimpleNamespace(search=_Search())
    host.context = types.SimpleNamespace(verbose=False)
    collected = list(host._poll_messages('c1', after_key='', max_wait=5, sleep=lambda s: None))
    roles = [m['role'] for m in collected]
    assert roles[-1] == 'chariot'
    assert collected[-1]['content'] == 'final answer'

def test_poll_messages_surfaces_persistent_errors(host):
    class _Search:
        def by_key_prefix(self, prefix, user=False):
            raise RuntimeError('search down')
    host.sdk = types.SimpleNamespace(search=_Search())
    host.context = types.SimpleNamespace(verbose=False)
    from praetorian_cli.ui.console.commands.marcus import MarcusError
    with pytest.raises(MarcusError):
        list(host._poll_messages('c1', after_key='', max_wait=2, sleep=lambda s: None,
                                 error_threshold=1))

def test_post_to_planner_guards_non_json_on_200(host):
    # 200 OK but body is not JSON -> must raise MarcusError (the JSON-parse guard)
    from praetorian_cli.ui.console.commands.marcus import MarcusError
    ok_but_bad = _FakeResp(200, body='not json', ok=True)
    def _raise(): raise ValueError('no json')
    ok_but_bad.json = _raise
    h, _ = _make_host_for_post(ok_but_bad)
    with pytest.raises(MarcusError):
        h._post_to_planner('hi')


# ── FIX 1: Ctrl-C during the initial POST ────────────────────────────────────

def test_ctrl_c_during_initial_request_returns_none(host):
    """KeyboardInterrupt during _post_to_planner must return None and print cancel msg."""
    import contextlib

    def _boom(m):
        raise KeyboardInterrupt()

    host._post_to_planner = _boom
    printed = []

    class _Console:
        def print(self, *a, **k): printed.append(' '.join(str(x) for x in a))
        def status(self, *a, **k): return contextlib.nullcontext()

    host.console = _Console()
    host.colors = {'primary': 'red'}
    host.context = types.SimpleNamespace(account=None, mode='agent', conversation_id=None,
                                         verbose=False)

    class _Search:
        def by_key_prefix(self, prefix, user=False): return ([], None)

    host.sdk = types.SimpleNamespace(search=_Search())
    result = host._send_to_marcus('hi')
    assert result is None
    assert any('cancel' in p.lower() or 'interrupt' in p.lower() for p in printed)


# ── FIX 2: Network exceptions in _post_to_planner become MarcusError ─────────

def test_post_to_planner_network_error_becomes_marcus_error(host):
    """RequestException from chariot_request must be re-raised as MarcusError."""
    from requests.exceptions import RequestException
    from praetorian_cli.ui.console.commands.marcus import MarcusError

    h, _ = _make_host_for_post(RequestException('boom'))
    with pytest.raises(MarcusError):
        h._post_to_planner('hi')


# ── FIX 3 + 4: Guard result type and non-dict poll items ─────────────────────

def test_poll_messages_skips_non_dict_items(host):
    """Non-dict items in the message list must be silently skipped."""
    msgs = [
        {'key': '#message#c1#001', 'role': 'tool call', 'content': '{}'},
        'garbage',
        {'key': '#message#c1#002', 'role': 'chariot', 'content': 'done'},
    ]
    call_count = {'n': 0}

    class _Search:
        def by_key_prefix(self, prefix, user=False):
            call_count['n'] += 1
            return (msgs, None)

    host.sdk = types.SimpleNamespace(search=_Search())
    host.context = types.SimpleNamespace(verbose=False)
    collected = list(host._poll_messages('c1', after_key='', max_wait=5, sleep=lambda s: None))
    roles = [m['role'] for m in collected]
    assert 'chariot' in roles
    assert collected[-1]['content'] == 'done'


# ─────────────────────────────────────────────────────────────────────────────

# ── WebSocket transport with polling fallback ────────────────────────────────

def _ws_host(ws_url=None, token='jwt-tok', account=None):
    h = _Host()

    class _KC:
        def websocket_url(self): return ws_url
        def token(self): return token
    _KC.account = account

    class _Search:
        calls = []
        def by_key_prefix(self, prefix, user=False):
            raise AssertionError('by_key_prefix should not be called in this test')

    h.sdk = types.SimpleNamespace(keychain=_KC(), search=_Search())
    return h


def test_stream_uses_polling_when_no_ws_url(host):
    h = _ws_host(ws_url=None)
    sentinel = [{'key': 'a', 'role': 'chariot', 'content': 'polled'}]
    h._poll_messages = lambda cid, after_key='': iter(sentinel)
    h._ws_messages = lambda *a, **k: (_ for _ in ()).throw(
        AssertionError('ws should not be used when no url'))
    assert list(h._stream_messages('c1')) == sentinel


def test_stream_uses_ws_when_configured(host):
    h = _ws_host(ws_url='wss://x')
    ws_msgs = [{'key': '1', 'role': 'tool call', 'content': '{}'},
               {'key': '2', 'role': 'chariot', 'content': 'ws-done'}]
    h._ws_messages = lambda cid, after_key='': iter(ws_msgs)
    def _poll_boom(*a, **k):
        raise AssertionError('polling must not be called when ws works')
    h._poll_messages = _poll_boom
    assert list(h._stream_messages('c1')) == ws_msgs


def test_stream_falls_back_to_polling_on_ws_unavailable_before_yield(host):
    from praetorian_cli.ui.console.commands.marcus import _WSUnavailable
    h = _ws_host(ws_url='wss://x')
    def _ws_fail(cid, after_key=''):
        raise _WSUnavailable('connect failed')
        yield  # pragma: no cover (make it a generator)
    h._ws_messages = _ws_fail
    sentinel = [{'key': 'p', 'role': 'chariot', 'content': 'polled-fallback'}]
    h._poll_messages = lambda cid, after_key='': iter(sentinel)
    assert list(h._stream_messages('c1')) == sentinel


def test_stream_raises_if_ws_drops_after_yield(host):
    from praetorian_cli.ui.console.commands.marcus import _WSUnavailable, MarcusError
    h = _ws_host(ws_url='wss://x')
    def _ws_drop(cid, after_key=''):
        yield {'key': '1', 'role': 'tool call', 'content': '{}'}
        raise _WSUnavailable('dropped mid-stream')
    h._ws_messages = _ws_drop
    def _poll_boom(*a, **k):
        raise AssertionError('must not fall back to polling after yielding')
    h._poll_messages = _poll_boom
    with pytest.raises(MarcusError):
        list(h._stream_messages('c1'))


def test_ws_messages_yields_until_chariot(host):
    from unittest.mock import patch
    h = _Host()

    class _KC:
        account = None
        def websocket_url(self): return 'wss://x'
        def token(self): return 'jwt-tok'

    rounds = iter([
        [{'key': '#message#c1#001', 'role': 'tool call', 'content': '{}'}],
        [{'key': '#message#c1#001', 'role': 'tool call', 'content': '{}'},
         {'key': '#message#c1#002', 'role': 'chariot', 'content': 'final'}],
    ])

    class _Search:
        def by_key_prefix(self, prefix, user=False):
            return (next(rounds), None)

    h.sdk = types.SimpleNamespace(keychain=_KC(), search=_Search())

    class _FakeConn:
        def send(self, *a, **k): pass
        def recv(self, *a, **k): return ''
        def settimeout(self, *a, **k): pass
        def close(self, *a, **k): pass

    with patch('websocket.create_connection', return_value=_FakeConn()):
        collected = list(h._ws_messages('c1', after_key=''))

    roles = [m['role'] for m in collected]
    assert roles == ['tool call', 'chariot']
    assert collected[-1]['content'] == 'final'


def test_send_to_marcus_handles_ctrl_c(host):
    # _post_to_planner succeeds, but polling raises KeyboardInterrupt mid-stream
    host._post_to_planner = lambda m: {'conversation': {'uuid': 'c1'}}
    def _boom(*a, **k):
        raise KeyboardInterrupt()
    host._poll_messages = _boom
    printed = []
    class _Console:
        def print(self, *a, **k): printed.append(' '.join(str(x) for x in a))
        def status(self, *a, **k):
            import contextlib; return contextlib.nullcontext()
    host.console = _Console()
    host.colors = {'primary': 'red'}
    host.context = types.SimpleNamespace(account=None, mode='agent', conversation_id=None,
                                         verbose=False)
    class _Search:
        def by_key_prefix(self, prefix, user=False): return ([], None)
    class _KC:
        def websocket_url(self): return None
    host.sdk = types.SimpleNamespace(search=_Search(), keychain=_KC())
    result = host._send_to_marcus('hi')
    assert result is None
    assert any('cancel' in p.lower() or 'interrupt' in p.lower() for p in printed)
