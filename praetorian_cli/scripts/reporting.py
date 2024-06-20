"""
This script is used to help engineers quickly create and update findings in 
Chariot seamlessly.

Example usage:

  praetorian chariot list accounts --script reporting

Prerequisites:

  fzf
  git

"""
import glob
import os
import pty
import shutil
import click
import subprocess
from shutil import which
from praetorian_cli.handlers.utils import Status
from praetorian_cli.sdk.chariot import Chariot


def process(controller: Chariot, cmd: dict, cli_kwargs: dict, _):
    if which('fzf') is None:
        print("This script requires fzf. See instructions at https://github.com/junegunn/fzf?tab=readme-ov-file#installation.")
        return

    sow, asset_key = create_asset(controller)
    click.echo(f'Using asset - {asset_key}.')

    path = create_findings(controller)
    click.echo(f'Using finding - {path}.')

    risk_name, risk_key = create_risk(controller, asset_key, path)
    click.echo(f'Using risk - {risk_name}.')

    if click.prompt('Would you like to update the risk status?', type=bool, default=False):
        statuses = [status.name for status in Status['risk']]
        status = Status['risk'][fzf_generic(statuses)].value
        controller.update('risk', dict(
            key=risk_key, status=status, comment=''))

    upload = click.prompt(f'Upload {path} finding to Chariot?',
                          type=bool, default=True)
    if upload:
        controller.upload(path, f"definitions/{risk_name}")

    upload = True
    while upload:
        upload = click.prompt(
            'Upload any additional engagement files to Chariot', type=bool, default=False)
        if upload:
            path = fzf_file(click.prompt('Enter glob pattern to search for files',
                                         type=str, default='./**/*'))
            if click.prompt(f'Upload {path}', type=bool, default=True):
                controller.upload(
                    path, f"files/{sow}/{os.path.basename(path)}")


def create_asset(controller: Chariot) -> tuple[str, str, str, str]:
    previous_name = EnvManager().get('ASSET_NAME', None)
    key = EnvManager().get('ASSET_KEY', None)

    sow = prompt_and_set_env('SOW Number', '2024-02-1234')
    name = prompt_and_set_env('Asset Name', 'www.praetorian.com')

    if previous_name == name and key:
        click.echo(f'Asset already exists in the environment. {key}')
        if click.prompt(
                'Would you like to skip asset creation in Chariot (recommended)', type=bool, default=True):
            return (sow, key)

    click.echo('Creating asset...')
    asset = controller.add('asset', dict(dns=name, name=name, status='F'))
    key = asset[0]['key']
    EnvManager().set('ASSET_KEY', key)
    controller.add('asset/attribute',
                   {'key': key, 'name': sow, 'class': 'SOW'})
    click.echo(f'Asset created in Chariot - {key}')
    return (sow, key)


def create_findings(controller: Chariot) -> str:
    path = EnvManager().get('FINDING_TEMPLATE', '')
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

    EnvManager().set('FINDING_TEMPLATE', path)
    return path


def create_risk(controller: Chariot, asset_key: str, finding: str) -> tuple[str, str]:
    key = EnvManager().get('RISK_KEY', None)
    name = EnvManager().get('RISK_NAME', None)
    dns = key.split('#')[2] if key else None
    if key and dns == EnvManager().get('ASSET_NAME', None):
        click.echo(f'Risk {name} already exists in the environment for {dns}')
        if click.prompt(
                'Would you like to skip risk creation in Chariot (recommended)', type=bool, default=True):
            return (name, key)

    finding = os.path.basename(finding).replace('.md', '').replace('_', '-')
    name = prompt_and_set_env('Risk Name', finding).replace(' ', '-')
    risk = controller.add('risk', dict(
        key=asset_key, name=name, status='TI', comment=''))
    click.echo(f'Risk created in Chariot - {name}')

    EnvManager().set('RISK_KEY', risk['risks'][0]['key'])
    EnvManager().set('RISK_NAME', name)

    return (name, risk['risks'][0]['key'])


class EnvManager:
    _instance = None

    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super(EnvManager, cls).__new__(cls)
        return cls._instance

    def __init__(self, env_file='.env'):
        self.env_file = env_file
        self.env_vars = self._load_env_vars()

    def _load_env_vars(self):
        if not os.path.exists(self.env_file):
            return {}
        with open(self.env_file, 'r') as file:
            return {k: v for k, v in (line.strip().split('=', 1) for line in file if line.strip() and not line.startswith('#'))}

    def get(self, key: str, default_value: str):
        return self.env_vars.get('CHARIOT_' + key, default_value)

    def set(self, key: str, value: str):
        self.env_vars['CHARIOT_' + key] = value
        self._write_env_vars()

    def _write_env_vars(self):
        with open(self.env_file, 'w') as file:
            for k, v in self.env_vars.items():
                file.write(f'{k}={v}\n')


def prompt_and_set_env(message, default_value):
    var_name = message.upper().replace(' ', '_')
    value = click.prompt('Enter the ' + message, type=str,
                         default=EnvManager().get(var_name, default_value))
    EnvManager().set(var_name, value)
    return value


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
