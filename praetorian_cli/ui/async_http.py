import asyncio
import json
import threading
from collections.abc import Mapping
from concurrent.futures import (
    CancelledError as FutureCancelledError,
    TimeoutError as FutureTimeoutError,
)
from contextlib import suppress
from contextvars import ContextVar
from urllib.parse import urlparse

import aiohttp


_worker_cancel_event = ContextVar('hunt_worker_cancel_event', default=None)


async def run_in_worker(function, *args, **kwargs):
    """Run blocking SDK/render work with cancellation propagated to aiohttp."""
    cancel_event = threading.Event()
    token = _worker_cancel_event.set(cancel_event)
    worker = asyncio.create_task(
        asyncio.to_thread(function, *args, **kwargs)
    )
    try:
        return await asyncio.shield(worker)
    except asyncio.CancelledError:
        cancel_event.set()
        with suppress(asyncio.CancelledError, Exception):
            await asyncio.wait_for(asyncio.shield(worker), timeout=1)
        raise
    finally:
        _worker_cancel_event.reset(token)


class AiohttpResponse:
    """Small requests-compatible response used by the existing SDK entities."""

    def __init__(self, status, headers, body, url, reason=''):
        self.status_code = status
        self.status = status
        self.headers = headers
        self.content = body
        self.url = url
        self.reason = reason
        self.text = body.decode('utf-8', errors='replace')
        self.ok = 200 <= status < 300

    def json(self):
        return json.loads(self.text)


class SharedAiohttpSession:
    """One aiohttp ClientSession shared by all synchronous SDK worker calls.

    The session lives on a dedicated asyncio loop. Existing SDK methods continue
    to run in worker threads and block only those workers while the Textual event
    loop remains free to process keyboard and mouse events.
    """

    def __init__(self):
        self._loop = None
        self._session = None
        self._ready = threading.Event()
        self._thread = threading.Thread(
            target=self._run_loop,
            name='guard-hunt-http',
            daemon=True,
        )
        self._thread.start()
        if not self._ready.wait(timeout=10):
            raise RuntimeError('timed out starting shared Hunt HTTP session')

    def _run_loop(self):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        self._loop = loop
        self._session = loop.run_until_complete(self._create_session())
        self._ready.set()
        loop.run_forever()
        if not self._session.closed:
            loop.run_until_complete(self._session.close())
        loop.close()

    async def _create_session(self):
        connector = aiohttp.TCPConnector(limit=32, limit_per_host=16)
        return aiohttp.ClientSession(connector=connector, trust_env=True)

    def request(self, method, url, headers=None, **kwargs):
        if self._loop is None or self._session is None:
            raise RuntimeError('shared Hunt HTTP session is closed')
        timeout_seconds = _timeout_seconds(kwargs.pop('timeout', None))
        coroutine = self._request(
            method,
            url,
            headers=headers,
            timeout_seconds=timeout_seconds,
            **kwargs,
        )
        future = asyncio.run_coroutine_threadsafe(coroutine, self._loop)
        cancel_event = _worker_cancel_event.get()
        while True:
            if cancel_event is not None and cancel_event.is_set():
                future.cancel()
                raise FutureCancelledError()
            try:
                return future.result(timeout=0.05)
            except FutureTimeoutError:
                if future.done():
                    return future.result()
                continue

    async def _request(
        self,
        method,
        url,
        *,
        headers,
        timeout_seconds,
        **kwargs,
    ):
        proxies = kwargs.pop('proxies', None)
        if 'params' in kwargs:
            kwargs['params'] = _normalize_query_params(kwargs['params'])
        verify = kwargs.pop('verify', True)
        proxy = None
        if isinstance(proxies, dict):
            proxy = proxies.get(urlparse(url).scheme)
        connect_timeout, read_timeout = timeout_seconds
        timeout = aiohttp.ClientTimeout(
            total=None,
            sock_connect=connect_timeout,
            sock_read=read_timeout,
        )
        async with self._session.request(
            method,
            url,
            headers=headers,
            proxy=proxy,
            ssl=False if verify is False else None,
            timeout=timeout,
            **kwargs,
        ) as response:
            body = await response.read()
            return AiohttpResponse(
                response.status,
                dict(response.headers),
                body,
                str(response.url),
                response.reason or '',
            )

    def close(self):
        loop = self._loop
        if loop is None:
            return
        future = asyncio.run_coroutine_threadsafe(self._shutdown(), loop)
        try:
            future.result(timeout=10)
        except FutureTimeoutError:
            future.cancel()
            loop.call_soon_threadsafe(loop.stop)
        self._thread.join(timeout=10)
        self._loop = None
        self._session = None

    async def _shutdown(self):
        current = asyncio.current_task()
        pending = [
            task for task in asyncio.all_tasks()
            if task is not current and not task.done()
        ]
        for task in pending:
            task.cancel()
        if pending:
            await asyncio.gather(*pending, return_exceptions=True)
        await self._session.close()
        self._loop.call_soon(self._loop.stop)


class InstalledAiohttpSession:
    """Temporarily replace a Chariot requests.Session for Hunt UI lifetime."""

    def __init__(self, sdk):
        self.sdk = sdk
        self.original = getattr(sdk, 'session', None)
        self.shared = None
        self.owns_session = False
        if isinstance(self.original, SharedAiohttpSession):
            self.shared = self.original
        elif self.original is not None:
            self.shared = SharedAiohttpSession()
            self.owns_session = True
            sdk.session = self.shared

    def close(self):
        if self.shared is None:
            return
        if self.owns_session:
            self.sdk.session = self.original
            self.shared.close()
        self.shared = None


def install_shared_aiohttp_session(sdk):
    return InstalledAiohttpSession(sdk)


def _normalize_query_params(params):
    """Match requests' permissive query encoding for aiohttp/yarl."""
    if params is None or isinstance(params, (str, bytes)):
        return params
    items = params.items() if isinstance(params, Mapping) else params
    normalized = []
    for key, value in items:
        values = value if isinstance(value, (list, tuple)) else (value,)
        for item in values:
            if item is None:
                continue
            normalized.append((str(key), _normalize_query_value(item)))
    return normalized


def _normalize_query_value(value):
    if isinstance(value, bool):
        return str(value)
    if isinstance(value, (str, int, float, bytes)):
        return value
    return str(value)


def _timeout_seconds(value):
    if isinstance(value, (int, float)) and value > 0:
        timeout = float(value)
        return timeout, timeout
    if isinstance(value, tuple) and len(value) == 2:
        return tuple(
            float(item)
            if isinstance(item, (int, float)) and item > 0
            else None
            for item in value
        )
    return None, None
