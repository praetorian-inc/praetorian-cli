"""
This script is used to help engineers quickly create and update findings in 
Chariot seamlessly. The recommended workflow is to create an .env.[risk] per
risk to cache the risk information created in Chariot.

Example usage:

  praetorian chariot plugin report [.env.risk-name]

Prerequisites:

  fzf
  git

"""
import glob
import os
import pty
import shutil
import subprocess

import click

from praetorian_cli.handlers.utils import Status
from praetorian_cli.plugins.utils import requires
from praetorian_cli.sdk.chariot import Chariot


class ReportingPlugin():
    def __init__(self, controller: Chariot, env_file: str):
        self.controller = controller
        self.env_file = env_file
        self.env_manager = EnvManager(env_file)

    def workflow(self):
        sow, asset_key = self.create_asset()
        click.echo(f'Using asset - {asset_key}.')

        path = self.create_findings()
        click.echo(f'Using finding - {path}.')

        risk_name, risk_key = self.create_risk(asset_key, path)
        click.echo(f'Using risk - {risk_name}.')

        if click.prompt('Would you like to update the risk status?', type=bool, default=False):
            status = Status['risk'][fzf_generic(
                [status.name for status in Status['risk']])].value
            self.controller.update('risk', dict(
                key=risk_key, status=status, comment=''))

        if click.prompt(f'Upload {path} finding to Chariot? (RECOMMENDED)',
                        type=bool, default=True):
            self.controller.upload(path, f"definitions/{sow}/{risk_name}")

        while click.prompt(
                'Upload any additional engagement files to Chariot', type=bool, default=False):
            path = fzf_file(click.prompt('Enter glob pattern to search for files',
                                         type=str, default='./**/*'))
            if click.prompt(f'Upload {path}', type=bool, default=True):
                self.controller.upload(
                    path, f"files/{sow}/{os.path.basename(path)}")

    def create_asset(self) -> tuple[str, str, str, str]:
        previous_name = self.env_manager.get('ASSET_NAME', None)
        key = self.env_manager.get('ASSET_KEY', None)

        sow = self.prompt_and_set_env('SOW Number', '2024-02-1234')
        name = self.prompt_and_set_env('Asset Name', 'www.praetorian.com')

        if previous_name == name and key:
            click.echo(f'Asset already exists in the environment. {key}')
            if click.prompt(
                    'Would you like to skip asset creation in Chariot (recommended)', type=bool, default=True):
                return (sow, key)

        click.echo('Creating asset...')
        asset = self.controller.add('asset', dict(dns=name, name=name, status='F'))
        key = asset[0]['key']
        self.env_manager.set('ASSET_KEY', key)
        self.controller.add('attribute',
                            {'key': key, 'name': sow, 'class': 'SOW'})
        click.echo(f'Asset created in Chariot - {key}')
        return (sow, key)

    def create_findings(self) -> str:
        path = self.env_manager.get('FINDING_TEMPLATE', '')
        if os.path.exists(path) and click.prompt(f'Local finding found. Reuse - {path}', type=bool, default=True):
            return path

        if click.prompt(
                'Would you like to use a VKB template?', type=bool, default=True):
            click.echo('Pulling the latest version of the vkb-templates...')
            if os.path.isdir(os.path.expanduser('~/.vkb-templates')):
                subprocess.run(
                    ['git', '-C', os.path.expanduser('~/.vkb-templates'), 'pull'], check=True)
            else:
                subprocess.run(['git', 'clone', 'git@github.com:praetorian-inc/vkb-templates.git',
                                os.path.expanduser('~/.vkb-templates')], check=True)

            template = fzf_file('~/.vkb-templates/**/*.md')
            path = click.prompt('Enter the local path to copy the finding',
                                type=str, default=os.path.basename(template))
            shutil.copyfile(template, path)
        else:
            path = fzf_file(click.prompt('Enter glob pattern to search for your finding',
                                         type=str, default='./**/*.md'))

        self.env_manager.set('FINDING_TEMPLATE', path)
        return path

    def create_risk(self, asset_key: str, finding: str) -> tuple[str, str]:
        key = self.env_manager.get('RISK_KEY', None)
        name = self.env_manager.get('RISK_NAME', None)
        dns = key.split('#')[2] if key else None
        if key and dns == self.env_manager.get('ASSET_NAME', None):
            click.echo(f'Risk {name} already exists in the environment for {dns}')
            if click.prompt(
                    'Would you like to skip risk creation in Chariot (recommended)', type=bool, default=True):
                return (name, key)

        finding = os.path.basename(finding).replace('.md', '').replace('_', '-')
        name = self.prompt_and_set_env('Risk Name', finding).replace(' ', '-')
        risk = self.controller.add('risk', dict(
            key=asset_key, name=name, status='TI', comment=''))
        click.echo(f'Risk created in Chariot - {name}')

        self.env_manager.set('RISK_KEY', risk['risks'][0]['key'])
        self.env_manager.set('RISK_NAME', name)

        return (name, risk['risks'][0]['key'])

    def prompt_and_set_env(self, message, default_value):
        var_name = message.upper().replace(' ', '_')
        value = click.prompt('Enter the ' + message, type=str,
                             default=self.env_manager.get(var_name, default_value))
        self.env_manager.set(var_name, value)
        return value


@requires('fzf',
          'This script requires fzf. See instructions at https://github.com/junegunn/fzf?tab=readme-ov-file#installation.')
@requires('git', 'This script requires git. See instructions at https://git-scm.com/downloads.')
def run(controller, env_file: str):
    """ Execute the reporting workflow """
    ReportingPlugin(controller, env_file).workflow()


class EnvManager:
    _instance = None

    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super(EnvManager, cls).__new__(cls)
        return cls._instance

    def __init__(self, env_file):
        self.env_file = env_file
        self.env_vars = self._load_env_vars()

    def _load_env_vars(self):
        if not os.path.exists(self.env_file):
            return {}
        with open(self.env_file, 'r') as file:
            return {k: v for k, v in
                    (line.strip().split('=', 1) for line in file if line.strip() and not line.startswith('#'))}

    def get(self, key: str, default_value: str):
        return self.env_vars.get('CHARIOT_' + key, default_value)

    def set(self, key: str, value: str):
        self.env_vars['CHARIOT_' + key] = value
        self._write_env_vars()

    def _write_env_vars(self):
        with open(self.env_file, 'w') as file:
            for k, v in self.env_vars.items():
                file.write(f'{k}={v}\n')


def fzf_file(glob_path) -> str:
    files = glob.glob(os.path.expanduser(glob_path), recursive=True)
    return fzf_generic(files)


def fzf_generic(items) -> str:
    master, slave = pty.openpty()

    with subprocess.Popen(['fzf'], stdin=subprocess.PIPE, stdout=slave) as process:
        process.stdin.write('\n'.join(items).encode())
        process.stdin.close()
        process.wait()

    selected = os.read(master, 1024).decode().strip()

    os.close(master)
    os.close(slave)

    return selected
