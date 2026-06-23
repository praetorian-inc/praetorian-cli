import json
import os
import shlex
import shutil
import subprocess
import sys
import tempfile
import webbrowser
from datetime import datetime

import click

from praetorian_cli.handlers.chariot import chariot
from praetorian_cli.handlers.cli_decorators import cli_handler
from praetorian_cli.handlers.utils import error
from praetorian_cli.handlers.vm_proxy import build_code_server_url, run_ws_proxy
from praetorian_cli.sdk.model.vm import MODES, TIERS, status_label


@chariot.group()
def vm():
    """ Manage ad-hoc Engineer VM cloud workspaces (Praetorian engineers only).

    Authorization is enforced server-side: every route is gated to Praetorian
    analysts, so a non-Praetorian caller gets a 403. The group itself stays a
    plain passthrough so `--help` works without credentials configured.
    """


@vm.command('list')
@cli_handler
@click.pass_context
def list_vms(ctx, sdk):
    """ List your Engineer VMs. """
    click.echo(format_vm_table(sdk.vms.list()))


@vm.command('launch')
@cli_handler
@click.option('--tier', type=click.Choice(TIERS), default='light', show_default=True,
              help='Instance class.')
@click.option('--mode', type=click.Choice(MODES), default='code-review', show_default=True,
              help='Auto-start set baked into the AMI.')
@click.option('--restore-snapshot', 'restore_snapshot_id', default='',
              help='Restore the data volume from a tenant-owned snapshot id.')
@click.pass_context
def launch(ctx, sdk, tier, mode, restore_snapshot_id):
    """ Launch a new Engineer VM. """
    new_vm = sdk.vms.launch(tier=tier, mode=mode, restore_snapshot_id=restore_snapshot_id)
    vm_id = new_vm.get('vm_id', '?')
    click.echo(f"Launched engineer VM {vm_id} "
               f"(status: {status_label(new_vm.get('status', ''))}, tier: {tier}, mode: {mode}).")
    click.echo(f"  It takes a couple minutes to reach 'running'. Track it with: "
               f"praetorian vm status {vm_id}")


@vm.command('status')
@cli_handler
@click.argument('vm_id', required=True)
@click.pass_context
def status(ctx, sdk, vm_id):
    """ Show one VM's full details. """
    click.echo(json.dumps(sdk.vms.get(vm_id), indent=2))


@vm.command('pause')
@cli_handler
@click.argument('vm_id', required=True)
@click.pass_context
def pause(ctx, sdk, vm_id):
    """ Stop a VM, keeping its volume and SG for a later resume. """
    result = sdk.vms.pause(vm_id)
    click.echo(f"Paused {vm_id} (status: {status_label(result.get('status', ''))}).")


@vm.command('resume')
@cli_handler
@click.argument('vm_id', required=True)
@click.pass_context
def resume(ctx, sdk, vm_id):
    """ Start a paused VM back up. """
    result = sdk.vms.resume(vm_id)
    click.echo(f"Resumed {vm_id} (status: {status_label(result.get('status', ''))}).")


@vm.command('extend')
@cli_handler
@click.argument('vm_id', required=True)
@click.option('--hours', type=int, default=0,
              help='Hours to push expiry out by (server defaults + clamps to the ceiling).')
@click.pass_context
def extend(ctx, sdk, vm_id, hours):
    """ Extend a VM's soft expiry. """
    result = sdk.vms.extend(vm_id, hours)
    click.echo(f"Extended {vm_id}; new expiry: {fmt_epoch(result.get('expiry_at'))}.")


@vm.command('terminate')
@cli_handler
@click.argument('vm_id', required=True)
@click.option('--yes', is_flag=True, help='Skip the confirmation prompt.')
@click.pass_context
def terminate(ctx, sdk, vm_id, yes):
    """ Snapshot the data volume, then terminate the VM. """
    if not yes:
        click.confirm(f"Terminate engineer VM {vm_id}? Its data volume is snapshotted first.",
                      abort=True)
    result = sdk.vms.terminate(vm_id)
    click.echo(f"Terminated {vm_id} (status: {status_label(result.get('status', ''))}).")


@vm.command('ssh')
@cli_handler
@click.argument('vm_id', required=True)
@click.option('-u', '--user', default='engineer', show_default=True,
              help='Login user on the VM.')
@click.argument('args', nargs=-1)
@click.pass_context
def ssh(ctx, sdk, vm_id, user, args):
    """ SSH into an Engineer VM over a 15-min vm-bound CA cert.

    Generates an ephemeral keypair, mints a certificate scoped to this VM, and
    execs ssh through the gateway ProxyCommand. Extra ssh flags after VM_ID are
    forwarded to ssh. No AWS credentials are used.
    """
    ssh_bin = shutil.which('ssh')
    keygen_bin = shutil.which('ssh-keygen')
    if not ssh_bin or not keygen_bin:
        error('ssh and ssh-keygen must be installed and on PATH.')

    workdir = tempfile.mkdtemp(prefix='guard-vm-ssh-')
    try:
        key_path = os.path.join(workdir, 'id_ed25519')
        subprocess.run([keygen_bin, '-t', 'ed25519', '-N', '', '-q', '-f', key_path], check=True)
        with open(f'{key_path}.pub') as f:
            public_key = f.read().strip()

        resp = sdk.vms.ssh_cert(vm_id, public_key)
        certificate = resp.get('certificate')
        gateway = resp.get('gateway_url')
        if not certificate:
            error('Server did not return an SSH certificate.')
        if not gateway:
            error('Server did not return a gateway URL.')

        cert_path = f'{key_path}-cert.pub'
        with open(cert_path, 'w') as f:
            f.write(certificate if certificate.endswith('\n') else certificate + '\n')

        proxy_command = ' '.join(shlex.quote(a) for a in proxy_argv(sdk, vm_id, gateway))

        known_hosts = os.path.join(workdir, 'known_hosts')
        ssh_argv = [
            ssh_bin,
            '-i', key_path,
            '-o', f'CertificateFile={cert_path}',
            '-o', f'ProxyCommand={proxy_command}',
            '-o', 'IdentitiesOnly=yes',
            '-o', 'StrictHostKeyChecking=accept-new',
            '-o', f'UserKnownHostsFile={known_hosts}',
        ]
        ssh_argv.extend(args)
        ssh_argv.append(f'{user}@{vm_id}')

        click.echo(f'→ Connecting to engineer VM {vm_id} (cert valid ~15 min)…', err=True)
        result = subprocess.run(ssh_argv)
        sys.exit(result.returncode)
    finally:
        shutil.rmtree(workdir, ignore_errors=True)


@vm.command('code-server')
@cli_handler
@click.argument('vm_id', required=True)
@click.option('--no-browser', is_flag=True, help='Print the URL instead of opening a browser.')
@click.pass_context
def code_server(ctx, sdk, vm_id, no_browser):
    """ Open the browser code-server IDE for a VM in a new tab. """
    resp = sdk.vms.code_server_token(vm_id)
    token = resp.get('token')
    gateway = resp.get('gateway_url')
    if not token or not gateway:
        error('Server did not return a code-server token/gateway.')
    url = build_code_server_url(gateway, token)
    if no_browser:
        click.echo(url)
        return
    click.echo(f'Opening code-server for {vm_id} in your browser…', err=True)
    if not webbrowser.open(url):
        click.echo(url)


@vm.command('proxy', hidden=True)
@click.argument('vm_id', required=True)
@click.option('--gateway', required=True)
@click.option('--target', default='ssh')
@click.pass_obj
def proxy(sdk, vm_id, gateway, target):
    """ Internal: the ssh ProxyCommand. Bridges stdin/stdout to the gateway over WS. """
    token = sdk.keychain.token()
    account = sdk.keychain.account or ''
    sys.exit(run_ws_proxy(gateway, token, vm_id, target, account))


# --- helpers -----------------------------------------------------------------

def proxy_nesting(prog_basename: str) -> list:
    """ The command path to reach `vm proxy` for a given entry point: the `guard`
        entry exposes commands flat (`guard vm proxy`); `praetorian` nests them
        under the `chariot` group (`praetorian chariot vm proxy`). """
    return ['chariot', 'vm'] if prog_basename.lower().startswith('praetorian') else ['vm']


def proxy_argv(sdk, vm_id: str, gateway: str) -> list:
    """ Build the argv ssh runs as its ProxyCommand. Re-invokes the SAME entry
        point the user used (so profile/auth and command nesting match), reading
        the JWT fresh inside the spawned process — no token ever lands in argv. """
    invoked = os.path.basename(sys.argv[0]).lower()
    if invoked.startswith('guard'):
        prog = shutil.which('guard') or shutil.which('praetorian') or sys.argv[0]
    else:
        prog = shutil.which('praetorian') or shutil.which('guard') or sys.argv[0]
    nesting = proxy_nesting(os.path.basename(prog))
    return [prog] + global_opts(sdk) + nesting + \
        ['proxy', vm_id, '--gateway', gateway, '--target', 'ssh']


def global_opts(sdk) -> list:
    """ The top-level --profile/--account flags, which must precede the
        subcommand when re-invoking the CLI as the ProxyCommand. """
    opts = ['--profile', sdk.keychain.profile]
    if sdk.keychain.account:
        opts += ['--account', sdk.keychain.account]
    return opts


def fmt_epoch(ts) -> str:
    if not ts:
        return '-'
    try:
        return datetime.fromtimestamp(int(ts)).strftime('%Y-%m-%d %H:%M')
    except (ValueError, OverflowError, OSError):
        return str(ts)


def format_vm_table(vms: list) -> str:
    """ Render the VM list as a fixed-width table. """
    if not vms:
        return 'No engineer VMs.'
    header = ('VM ID', 'STATUS', 'TIER', 'MODE', 'PRIVATE IP', 'EXPIRES')
    rows = [header]
    for v in vms:
        rows.append((
            v.get('vm_id', ''),
            status_label(v.get('status', '')),
            v.get('tier', '') or '-',
            v.get('mode', '') or '-',
            v.get('private_ip', '') or '-',
            fmt_epoch(v.get('expiry_at')),
        ))
    widths = [max(len(row[i]) for row in rows) for i in range(len(header))]
    return '\n'.join('  '.join(cell.ljust(widths[i]) for i, cell in enumerate(row)) for row in rows)
