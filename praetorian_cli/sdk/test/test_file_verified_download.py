import hashlib
from pathlib import Path
from types import SimpleNamespace

import pytest

from praetorian_cli.sdk.entities import files as files_module
from praetorian_cli.sdk.entities.files import Files


class FakeResponse:
    def __init__(self, body=None, chunks=None, status_code=200):
        self.body = body or {}
        self.chunks = chunks or []
        self.status_code = status_code
        self.ok = 200 <= status_code < 300
        self.text = ''

    def json(self):
        return self.body

    def iter_content(self, chunk_size):
        assert chunk_size == 1024 * 1024
        yield from self.chunks

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False


class FakeAPI:
    def __init__(self, proxy=''):
        self.proxy = proxy
        self.search = SimpleNamespace(
            by_exact_key=lambda _key: (_ for _ in ()).throw(
                AssertionError('verified downloads must not require file indexing')
            )
        )
        self.calls = []

    def url(self, path):
        assert path == '/file'
        return path

    def chariot_request(self, method, url, params):
        self.calls.append((method, url, params))
        return FakeResponse({'url': 'https://s3.example/proof'})


def test_save_verified_streams_and_atomically_publishes_file(monkeypatch, tmp_path):
    content = b'proof-content'
    remote_path = 'proofs/endpoint-sessions/session/op/artifact/proof.txt'
    api = FakeAPI()
    request_calls = []

    def get(url, stream, timeout, **kwargs):
        request_calls.append((url, stream, timeout, kwargs))
        return FakeResponse(chunks=[content[:5], content[5:]])

    monkeypatch.setattr(files_module.requests, 'get', get)

    local_path = Files(api).save_verified(
        remote_path,
        len(content),
        hashlib.sha256(content).hexdigest(),
        str(tmp_path),
    )

    assert Path(local_path).read_bytes() == content
    assert api.calls == [('GET', '/file', {'name': remote_path})]
    assert request_calls[0][0:2] == ('https://s3.example/proof', True)
    assert not list(tmp_path.glob('.praetorian-download-*'))


def test_save_verified_uses_sdk_proxy_without_auth_headers(monkeypatch, tmp_path):
    request = {}

    def get(url, **kwargs):
        request.update({'url': url, **kwargs})
        return FakeResponse(chunks=[b'proof'])

    monkeypatch.setattr(files_module.requests, 'get', get)

    Files(FakeAPI(proxy='http://proxy.example:8080')).save_verified(
        'proofs/endpoint-sessions/session/op/artifact/proof.txt',
        5,
        hashlib.sha256(b'proof').hexdigest(),
        str(tmp_path),
    )

    assert request['proxies'] == {
        'http': 'http://proxy.example:8080',
        'https': 'http://proxy.example:8080',
    }
    assert request['verify'] is False
    assert 'headers' not in request


def test_save_verified_accepts_empty_artifact(monkeypatch, tmp_path):
    monkeypatch.setattr(
        files_module.requests,
        'get',
        lambda *_args, **_kwargs: FakeResponse(chunks=[]),
    )

    local_path = Files(FakeAPI()).save_verified(
        'proofs/endpoint-sessions/session/op/artifact/empty.txt',
        0,
        hashlib.sha256(b'').hexdigest(),
        str(tmp_path),
    )

    assert Path(local_path).read_bytes() == b''


def test_save_verified_resolves_default_directory_at_call_time(
    monkeypatch,
    tmp_path,
):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(
        files_module.requests,
        'get',
        lambda *_args, **_kwargs: FakeResponse(chunks=[b'proof']),
    )

    local_path = Files(FakeAPI()).save_verified(
        'proofs/endpoint-sessions/session/op/artifact/proof.txt',
        5,
        hashlib.sha256(b'proof').hexdigest(),
    )

    assert Path(local_path).parent == tmp_path


def test_failed_verification_preserves_existing_destination(monkeypatch, tmp_path):
    remote_path = 'proofs/endpoint-sessions/session/op/artifact/proof.txt'
    destination = tmp_path / Files(FakeAPI()).sanitize_filename(remote_path)
    destination.write_bytes(b'existing')
    monkeypatch.setattr(
        files_module.requests,
        'get',
        lambda *_args, **_kwargs: FakeResponse(chunks=[b'wrong']),
    )

    with pytest.raises(ValueError, match='failed size or SHA-256'):
        Files(FakeAPI()).save_verified(
            remote_path,
            5,
            hashlib.sha256(b'proof').hexdigest(),
            str(tmp_path),
        )

    assert destination.read_bytes() == b'existing'
    assert not list(tmp_path.glob('.praetorian-download-*'))


def test_download_larger_than_authorized_size_is_stopped(monkeypatch, tmp_path):
    monkeypatch.setattr(
        files_module.requests,
        'get',
        lambda *_args, **_kwargs: FakeResponse(chunks=[b'too-large']),
    )

    with pytest.raises(ValueError, match='exceeded its expected size'):
        Files(FakeAPI()).save_verified(
            'proofs/endpoint-sessions/session/op/artifact/proof.txt',
            5,
            hashlib.sha256(b'proof').hexdigest(),
            str(tmp_path),
        )

    assert not list(tmp_path.glob('.praetorian-download-*'))
