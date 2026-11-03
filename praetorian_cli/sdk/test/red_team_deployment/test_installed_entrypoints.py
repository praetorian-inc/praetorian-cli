"""Actual installed entrypoint scenarios; also executable with --smoke."""

import json
import os
import shutil
import subprocess
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest

from conftest import (
    CONTEXT, ENQUEUED, JOB_ID, PREFIX, SECRET, STATE,
    assert_no_execute, assert_preview_rendered, deployment_http, keychain_text,
    lifecycle_calls, safe_preview,
)


@pytest.mark.parametrize('entrypoint,prefix', [('guard', []), ('praetorian', ['chariot'])])
def test_installed_entrypoint_loopback_smoke(tmp_path, entrypoint, prefix):
    """Independent installed launcher, real auth/SDK HTTP; parent can select -k smoke."""
    executable = shutil.which(entrypoint)
    assert executable is not None, f'Install the actual {entrypoint} console entrypoint before smoke'
    root = Path(__file__).resolve().parents[4]
    env = {key: value for key, value in os.environ.items()
           if not key.startswith(('PRAETORIAN_', 'CHARIOT_', 'AWS_'))
           and not key.lower().endswith('_proxy')}
    env.update(HOME=str(tmp_path), USERPROFILE=str(tmp_path), PYTHONPATH=str(root),
               AWS_EC2_METADATA_DISABLED='true', PRAETORIAN_CLI_ALLOW_HTTP_LOOPBACK='1',
               PRAETORIAN_CLI_DISABLE_UPDATE_CHECK='1')
    with deployment_http() as boundary:
        directory = tmp_path / '.praetorian'
        directory.mkdir()
        (directory / 'keychain.ini').write_text(keychain_text(boundary.url))
        command = [executable, '--profile', 'RT isolated', '--account', 'selected-engagement'] + prefix + ['red-team', 'deployment']
        inventory = subprocess.run(command + ['inventory'], env=env, cwd=root,
                                   capture_output=True, text=True, timeout=30)
        assert inventory.returncode == 0, inventory.stdout + inventory.stderr
        assert json.loads(inventory.stdout)['status'] == 'missing'
        declined = subprocess.run(command + ['delete'], input='y\n', env=env, cwd=root,
                                  capture_output=True, text=True, timeout=30)
        assert declined.returncode == 2, declined.stdout + declined.stderr
        assert_preview_rendered(declined.stdout)
        assert_no_execute(boundary)
        boundary.preview = safe_preview('apply')
        config = tmp_path / 'configuration.json'
        config.write_text(json.dumps(STATE))
        approved = subprocess.run(command + ['apply', '--config-file', str(config), '--tag', 'v1.2.3', '--yes'],
                                  env=env, cwd=root, capture_output=True, text=True, timeout=30)
        assert approved.returncode == 0, approved.stdout + approved.stderr
        assert_preview_rendered(approved.stdout, 'apply')
        assert JOB_ID in approved.stdout and ENQUEUED in approved.stdout
        assert SECRET not in approved.stdout + approved.stderr
        calls = lifecycle_calls(boundary)
        assert [(c['method'], c['target']) for c in calls] == [
            ('GET', PREFIX + 'inventory'), ('POST', PREFIX + 'preview'),
            ('POST', PREFIX + 'preview'), ('POST', PREFIX + 'execute'),
        ]
        assert calls[-1]['body'] == calls[-2]['body'] | {'configuration_context_sha256': CONTEXT}
        assert calls[-1]['body']['state'] == STATE
        assert all(c['headers']['account'] == 'selected-engagement' for c in calls)
        print(f'{entrypoint}: inventory exit 0, piped-y delete exit 2/no execute, approved apply exit 0; exact body/context retained')



if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(description='Run isolated installed-entrypoint smoke without pytest collection.')
    parser.add_argument('--smoke', action='store_true', required=True)
    parser.parse_args()
    for name, command_prefix in [('guard', []), ('praetorian', ['chariot'])]:
        with TemporaryDirectory(prefix='eng-10837-cli-smoke-') as home:
            test_installed_entrypoint_loopback_smoke(Path(home), name, command_prefix)
