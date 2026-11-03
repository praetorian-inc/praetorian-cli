"""ENG-10837: public Click trees through real SDK requests to an owned HTTP server.

The HTTP fixture models only the documented safe API boundary, not backend
redaction, authorization or Terraform. No operator profile or cloud is used.
Library discovery: stdlib http.server/contextlib/subprocess cover the fixture;
reuse test_async_http.py's loopback server ownership pattern and existing
CliRunner/root-command conventions. No new dependency or production harness.
"""

import json
import os
import sys
import threading
from contextlib import contextmanager
from functools import partial
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from types import SimpleNamespace
from urllib.parse import urlsplit
from unittest.mock import patch

import pytest
from click.testing import CliRunner

import praetorian_cli.main as cli_module
from praetorian_cli.sdk.keychain import Keychain


CONTEXT = 'c' * 64
INPUT_DIGEST = 'd' * 64
COMMIT = 'a' * 40
JOB_ID = '#job#red-team#apply /+?'
ENQUEUED = '2026-11-02T17:19:25.123456789+00:00'
SECRET = 'PRIVATE-INPUT-DO-NOT-PRINT-6971'
STATE = {'nodes': [], 'globals': {'password': SECRET}}
PREFIX = '/selected/red-team/deployment/'
INFRA = {'tag': 'v1.2.3', 'commit': COMMIT}


def safe_preview(action='delete'):
    deployment = {'project_id': 'engagement-rt-ab'}
    if action == 'launch':
        deployment = {'desired_id': 'engagement-rt', 'suffix_policy': 'random two-character suffix'}
    return {
        'action': action,
        'tenant_id': 'selected-engagement',
        'deployment': deployment,
        'change': {
            'summary': 'Reviewed requested configuration',
            'nodes': [{'id': 'node-1', 'type': 'phishkit', 'fields': [
                {'name': 'password', 'redacted': True},
            ]}],
        },
        'infra': dict(INFRA),
        'configuration_context_sha256': CONTEXT,
        'input_sha256': INPUT_DIGEST,
        'recorded_revision': 'recorded-revision-7',
    }



def operation(status='enqueued', action='delete'):
    return {
        'action': action, 'status': status, 'job_id': JOB_ID,
        'enqueued': ENQUEUED, 'deployment': {'project_id': 'engagement-rt-ab'},
        'message': 'Recorded operation status',
    }



class DeploymentHandler(BaseHTTPRequestHandler):
    """Serve the static safe boundary and record actual wire effects."""

    def do_GET(self):
        self.respond()

    def do_POST(self):
        self.respond()

    def respond(self):
        boundary = self.server.boundary
        raw = self.rfile.read(int(self.headers.get('Content-Length', '0')))
        path = urlsplit(self.path).path
        boundary.calls.append({
            'method': self.command, 'target': self.path,
            'headers': dict(self.headers),
            'body': json.loads(raw) if raw else None,
            'raw': raw,
        })
        status, payload = self.response_payload(path)
        encoded = json.dumps(payload).encode()
        self.send_response(status)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)

    def response_payload(self, path):
        boundary = self.server.boundary
        if path in boundary.errors:
            return boundary.errors[path]
        if path == '/selected/token':
            return 200, {'token': 'inert-loopback-token', 'expires_in': 3600}
        if path == PREFIX + 'inventory':
            return 200, boundary.inventory
        if path == PREFIX + 'preview':
            payload = boundary.preview
            if boundary.on_preview:
                boundary.on_preview()
            return 200, payload
        if path == PREFIX + 'execute':
            # Capture the human-visible output at the instant execute arrives.
            buffer = getattr(sys.stdout, 'buffer', None)
            if hasattr(buffer, 'getvalue'):
                boundary.output_before_execute = buffer.getvalue().decode()
            if boundary.on_execute:
                boundary.on_execute()
            return 200, boundary.result
        if path == PREFIX + 'results':
            return 200, boundary.result
        return 404, {'message': 'Unexpected route: no raw artifact access permitted'}

    def log_message(self, *_args):
        pass


@contextmanager
def deployment_http():
    """Static endpoint responses, captured wire effects; never echo a request."""
    boundary = SimpleNamespace(
        calls=[], preview=safe_preview(), result=operation(),
        inventory={'tenant_id': 'selected-engagement', 'status': 'missing',
                   'outputs': {'status': 'unavailable', 'reason': 'no recorded deployment'},
                   'history': []},
        errors={}, on_preview=None, on_execute=None, output_before_execute='',
    )

    server = ThreadingHTTPServer(('127.0.0.1', 0), DeploymentHandler)
    server.boundary = boundary
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    boundary.url = f'http://127.0.0.1:{server.server_port}'
    try:
        yield boundary
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def keychain_text(url):
    return (
        '[United States]\napi = ' + url + '/wrong-profile\n'
        'client_id = inert-default\napi_key_id = wrong-key\napi_key_secret = wrong-secret\n'
        '[RT isolated]\napi = ' + url + '/selected\n'
        'client_id = inert-selected\napi_key_id = fixture-key\n'
        'api_key_secret = fixture-secret\naccount = profile-engagement\n'
    )



@pytest.fixture
def api(tmp_path, monkeypatch):
    for name in tuple(os.environ):
        if name.startswith(('PRAETORIAN_', 'CHARIOT_', 'AWS_')) or name.lower().endswith('_proxy'):
            monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv('HOME', str(tmp_path))
    monkeypatch.setenv('AWS_EC2_METADATA_DISABLED', 'true')
    monkeypatch.setenv('PRAETORIAN_CLI_ALLOW_HTTP_LOOPBACK', '1')
    monkeypatch.setenv('PRAETORIAN_CLI_DISABLE_UPDATE_CHECK', '1')
    with deployment_http() as boundary:
        keychain_path = tmp_path / 'keychain.ini'
        keychain_path.write_text(keychain_text(boundary.url))
        # Redirect only config location; Keychain.load/headers/token and SDK HTTP
        # stay real, including inert API-key exchange with the owned server.
        monkeypatch.setattr(cli_module, 'Keychain', partial(Keychain, filepath=keychain_path))
        boundary.keychain_path = keychain_path
        yield boundary



class TerminalRunner(CliRunner):
    """CliRunner streams with terminal capabilities, not a mocked confirm."""
    def __init__(self, *args, tty=(True, True), **kwargs):
        super().__init__(*args, **kwargs)
        self.tty = tty

    @contextmanager
    def isolation(self, *args, **kwargs):
        with super().isolation(*args, **kwargs) as streams:
            with patch.object(sys.stdin, 'isatty', return_value=self.tty[0]), patch.object(
                sys.stdout, 'isatty', return_value=self.tty[1],
            ):
                yield streams



@pytest.fixture(params=['guard', 'praetorian'])
def invoke(request):
    root = cli_module.guard_main if request.param == 'guard' else cli_module.main
    prefix = [] if request.param == 'guard' else ['chariot']

    def run(args, *, input=None, terminal=False, account='selected-engagement'):
        options = ['--profile', 'RT isolated']
        if account is not None:
            options += ['--account', account]
        tty = terminal if isinstance(terminal, tuple) else (True, True)
        runner = TerminalRunner(tty=tty) if terminal else CliRunner()
        return runner.invoke(root, options + prefix + ['red-team', 'deployment'] + args, input=input)

    return run



def lifecycle_calls(api):
    return [call for call in api.calls if urlsplit(call['target']).path != '/selected/token']



def assert_no_execute(api):
    assert all(urlsplit(call['target']).path != PREFIX + 'execute' for call in api.calls)



def assert_preview_rendered(text, action='delete'):
    assert 'Redacted deployment preview:' in text
    assert 'selected-engagement' in text
    assert ('engagement-rt' if action == 'launch' else 'engagement-rt-ab') in text
    assert action in text
    assert CONTEXT in text
    assert 'recorded-revision-7' in text
    assert SECRET not in text

