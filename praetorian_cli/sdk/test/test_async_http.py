import asyncio
import json
import threading
import time
from concurrent.futures import Future
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from types import SimpleNamespace

import aiohttp
import pytest

from praetorian_cli.ui.async_http import (
    SharedAiohttpSession,
    _timeout_seconds,
    install_shared_aiohttp_session,
    run_in_worker,
)


class JsonHandler(BaseHTTPRequestHandler):
    requests = []
    slow_request_started = threading.Event()

    def do_GET(self):
        self.__class__.requests.append({
            'path': self.path,
            'authorization': self.headers.get('Authorization'),
        })
        body = json.dumps({'ok': True, 'path': self.path}).encode()
        if self.path == '/slow':
            self.__class__.slow_request_started.set()
            time.sleep(2)
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        try:
            self.wfile.write(body)
        except OSError:
            pass

    def log_message(self, *_args):
        pass


def test_shared_aiohttp_session_reuses_one_client_for_worker_requests():
    JsonHandler.requests = []
    server = ThreadingHTTPServer(('127.0.0.1', 0), JsonHandler)
    server_thread = threading.Thread(target=server.serve_forever, daemon=True)
    server_thread.start()
    shared = SharedAiohttpSession()
    client_session = shared._session
    try:
        url = f'http://127.0.0.1:{server.server_port}/status'
        first = shared.request(
            'GET',
            url,
            headers={'Authorization': 'Bearer test'},
            params={
                'page': 1,
                'exact': False,
                'enabled': True,
                'label': ['root', 'child'],
                'omitted': None,
            },
            timeout=2,
        )
        second = shared.request('GET', url, timeout=2)
    finally:
        shared.close()
        server.shutdown()
        server.server_close()
        server_thread.join(timeout=2)

    assert shared._session is None
    assert client_session.closed is True
    assert client_session.trust_env is True
    assert first.ok is True
    assert first.status_code == 200
    assert first.json() == {
        'ok': True,
        'path': (
            '/status?page=1&exact=False&enabled=True&label=root&label=child'
        ),
    }
    assert second.json()['path'] == '/status'
    assert JsonHandler.requests == [
        {
            'path': (
                '/status?page=1&exact=False&enabled=True&label=root&label=child'
            ),
            'authorization': 'Bearer test',
        },
        {'path': '/status', 'authorization': None},
    ]


@pytest.mark.parametrize(
    ('requests_timeout', 'connect_timeout', 'read_timeout'),
    [
        (3, 3.0, 3.0),
        ((2, 7), 2.0, 7.0),
        (None, None, None),
    ],
)
def test_request_timeout_maps_to_socket_timeouts(
    requests_timeout,
    connect_timeout,
    read_timeout,
):
    class Response:
        status = 200
        headers = {}
        url = 'https://example.test/status'
        reason = 'OK'

        async def __aenter__(self):
            return self

        async def __aexit__(self, *_args):
            pass

        async def read(self):
            return b'{}'

    class Session:
        def request(self, *_args, **kwargs):
            self.timeout = kwargs['timeout']
            return Response()

    shared = object.__new__(SharedAiohttpSession)
    shared._session = Session()

    asyncio.run(shared._request(
        'GET',
        'https://example.test/status',
        headers={},
        timeout_seconds=_timeout_seconds(requests_timeout),
    ))

    timeout = shared._session.timeout
    assert timeout.total is None
    assert timeout.sock_connect == connect_timeout
    assert timeout.sock_read == read_timeout


def test_completed_request_timeout_propagates_without_a_deadline(monkeypatch):
    future = Future()
    future.set_exception(aiohttp.ServerTimeoutError('request timed out'))
    shared = object.__new__(SharedAiohttpSession)
    shared._loop = object()
    shared._session = object()

    def submit(coroutine, _loop):
        coroutine.close()
        return future

    monkeypatch.setattr(asyncio, 'run_coroutine_threadsafe', submit)

    with pytest.raises(aiohttp.ServerTimeoutError, match='request timed out'):
        shared.request('GET', 'https://example.test/status')


def test_cancelled_worker_cancels_its_inflight_aiohttp_request():
    JsonHandler.requests = []
    JsonHandler.slow_request_started.clear()
    server = ThreadingHTTPServer(('127.0.0.1', 0), JsonHandler)
    server_thread = threading.Thread(target=server.serve_forever, daemon=True)
    server_thread.start()
    shared = SharedAiohttpSession()

    async def exercise():
        url = f'http://127.0.0.1:{server.server_port}/slow'
        task = asyncio.create_task(
            run_in_worker(shared.request, 'GET', url, timeout=5)
        )
        while not JsonHandler.slow_request_started.is_set():
            await asyncio.sleep(0.005)
        started = time.monotonic()
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        assert time.monotonic() - started < 1

    try:
        asyncio.run(exercise())
    finally:
        shared.close()
        server.shutdown()
        server.server_close()
        server_thread.join(timeout=3)


def test_install_restores_the_original_sdk_session():
    original = object()
    sdk = SimpleNamespace(session=original)

    installed = install_shared_aiohttp_session(sdk)
    nested = install_shared_aiohttp_session(sdk)
    try:
        assert isinstance(sdk.session, SharedAiohttpSession)
        assert sdk.session is installed.shared
        assert nested.shared is installed.shared
        assert nested.owns_session is False
    finally:
        nested.close()
        assert sdk.session is installed.shared
        installed.close()

    assert sdk.session is original
