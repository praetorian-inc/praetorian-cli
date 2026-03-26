import json
import time

import click

from praetorian_cli.handlers.chariot import chariot
from praetorian_cli.handlers.cli_decorators import cli_handler
from praetorian_cli.handlers.utils import print_json, error


# Friendly names for well-known agents — descriptions for the CLI help
FRIENDLY_NAMES = {
    'asset-analyzer': 'Deep-dive reconnaissance & risk mapping',
    'brutus':         'Credential attacks (SSH, RDP, FTP, SMB)',
    'julius':         'LLM/AI service fingerprinting',
    'augustus':        'LLM jailbreak & prompt injection attacks',
    'aurelius':       'Cloud infrastructure discovery (AWS/Azure/GCP)',
    'trajan':         'CI/CD pipeline security scanning',
    'priscus':        'Remediation retesting',
    'seneca':         'CVE research & exploit intelligence',
    'titus':          'Secret scanning & credential leak detection',
}


def resolve_capability(sdk, name):
    """Resolve a capability name to its metadata from the backend API.

    Checks FRIENDLY_NAMES for aliases, then queries the /capabilities/ endpoint.
    Returns dict with at minimum: name, target, description. Or None.
    """
    # Check backend capabilities
    try:
        caps = sdk.capabilities.list(name=name)
        if isinstance(caps, list):
            cap_list = caps
        elif isinstance(caps, dict):
            cap_list = caps.get('capabilities', caps.get('data', []))
        else:
            cap_list = []

        # Exact match first
        for c in cap_list:
            cap_name = c.get('name', '')
            if cap_name.lower() == name.lower():
                target = c.get('target', [])
                if isinstance(target, list):
                    target = target[0] if target else 'asset'
                return {
                    'name': cap_name,
                    'capability': cap_name,
                    'target_type': target,
                    'description': c.get('description', ''),
                    'executor': c.get('executor', ''),
                }
    except Exception:
        pass

    return None


def resolve_target(sdk, target_input, expected_type):
    """Resolve a friendly target (domain, IP, URL) to a Guard entity key.

    Uses sdk.search.fulltext() for resolution. Returns (key, warning) tuple.
    """
    if target_input.startswith('#'):
        return target_input, None

    # Use fulltext search from the SDK
    try:
        results, _ = sdk.search.fulltext(target_input, kind=expected_type, limit=10)
        if results:
            # Exact match on dns/name
            for r in results:
                if r.get('dns', '') == target_input or r.get('name', '') == target_input:
                    return r['key'], None
            return results[0]['key'], None
    except Exception:
        pass

    # Fallback: prefix search
    valid_types = {
        'asset': 'asset', 'port': 'port', 'webpage': 'webpage',
        'webapplication': 'webapplication', 'repository': 'asset',
        'risk': 'risk',
    }
    vtype = valid_types.get(expected_type, expected_type)
    try:
        results, _ = sdk.search.by_key_prefix(f'#{vtype}#{target_input}', pages=1)
        if results:
            return results[0]['key'], None
    except Exception:
        pass

    # Fallback: field search
    for field in ('dns', 'name'):
        try:
            results, _ = sdk.search.by_term(f'{field}:{target_input}', expected_type, pages=1)
            if results:
                return results[0]['key'], None
        except Exception:
            pass

    return None, f'Could not resolve "{target_input}" to a {expected_type}. Use a full Guard key (#asset#...) or check the entity exists.'


@chariot.group()
def run():
    """ Execute security tools against targets

    \b
    Targets can be Guard keys (#asset#...) or friendly names (example.com, 10.0.1.5).
    Use "guard run list" to see all available agents and capabilities.
    """
    pass


@run.command('tool')
@cli_handler
@click.argument('tool_name')
@click.argument('target')
@click.option('-c', '--config', 'extra_config', default='', help='Extra JSON config to merge')
@click.option('--credential', multiple=True, help='Credential ID(s) to use')
@click.option('--wait', is_flag=True, default=False, help='Wait for job completion and show results')
@click.option('--ask', 'use_agent', is_flag=True, default=False, help='Run via Marcus AI agent instead of direct job')
@click.option('--local', is_flag=True, default=False, help='Run locally using installed binary')
@click.option('--remote', is_flag=True, default=False, help='Force remote job execution on Guard backend')
def tool(sdk, tool_name, target, extra_config, credential, wait, use_agent, local, remote):
    """ Execute a named security tool against a target

    By default, runs LOCALLY if the binary is installed, otherwise schedules
    a remote job. Use --local or --remote to force.

    \b
    Example usages:
        guard run tool brutus 10.0.1.5
        guard run tool nuclei example.com --remote
        guard run tool titus github.com/org/repo
    """
    from praetorian_cli.runners.local import is_installed as _is_installed

    cap = resolve_capability(sdk, tool_name.lower())
    if not cap:
        error(f'Unknown capability: {tool_name}. Use "guard run capabilities" to see available capabilities.')

    # Decide local vs remote
    run_local = local or (not remote and not use_agent and _is_installed(tool_name.lower()))

    if run_local:
        _run_local(sdk, tool_name.lower(), target, extra_config)
    elif use_agent:
        target_key, warning = resolve_target(sdk, target, cap['target_type'])
        if not target_key:
            error(warning)
        if warning:
            click.echo(warning, err=True)
        _run_via_agent(sdk, cap, target_key)
    else:
        target_key, warning = resolve_target(sdk, target, cap['target_type'])
        if not target_key:
            error(warning)
        if warning:
            click.echo(warning, err=True)
        _run_direct(sdk, cap, target_key, extra_config, list(credential), wait)


@run.command('list')
@cli_handler
def list_tools(sdk):
    """ List named agents and their descriptions

    \b
    Example usage:
        guard run list
    """
    click.echo(f'\n{"Agent":<16} {"Description"}')
    click.echo(f'{"─"*16} {"─"*50}')
    for name, desc in sorted(FRIENDLY_NAMES.items()):
        click.echo(f'{name:<16} {desc}')
    click.echo(f'\nUse "guard run capabilities" for the full list of backend capabilities.')


@run.command('capabilities')
@cli_handler
@click.option('-n', '--name', default='', help='Filter by capability name')
@click.option('-t', '--target', default='', help='Filter by target type')
def capabilities(sdk, name, target):
    """ List all available capabilities from the backend

    \b
    Example usages:
        guard run capabilities
        guard run capabilities --name nuclei
        guard run capabilities --target asset
    """
    result = sdk.capabilities.list(name=name, target=target)
    print_json(result)


@run.command('install')
@cli_handler
@click.argument('tool_name')
@click.option('--force', is_flag=True, default=False, help='Reinstall even if already installed')
def install(sdk, tool_name, force):
    """ Install a Praetorian capability binary locally

    Downloads the latest release from GitHub and installs to ~/.praetorian/bin/.
    Requires the GitHub CLI (gh) to be installed and authenticated.

    \b
    Example usages:
        guard run install brutus
        guard run install all
    """
    from praetorian_cli.runners.local import install_tool, INSTALLABLE_TOOLS, is_installed

    if tool_name == 'all':
        for name in sorted(INSTALLABLE_TOOLS):
            try:
                if not force and is_installed(name):
                    click.echo(f'{name}: already installed')
                else:
                    click.echo(f'{name}: installing...', nl=False)
                    path = install_tool(name, force=force)
                    click.echo(f' {path}')
            except Exception as e:
                click.echo(f' FAILED: {e}', err=True)
        return

    try:
        click.echo(f'Installing {tool_name}...')
        path = install_tool(tool_name, force=force)
        click.echo(f'Installed: {path}')
    except Exception as e:
        error(str(e))


@run.command('installed')
@cli_handler
def installed(sdk):
    """ List locally installed capability binaries """
    from praetorian_cli.runners.local import list_installed, INSTALLABLE_TOOLS

    inst = list_installed()
    click.echo(f'\n{"Tool":<16} {"Status":<12} {"Path"}')
    click.echo(f'{"─"*16} {"─"*12} {"─"*50}')
    for name in sorted(INSTALLABLE_TOOLS):
        if name in inst:
            click.echo(f'{name:<16} {"installed":<12} {inst[name]}')
        else:
            click.echo(f'{name:<16} {"—":<12}')


def _run_direct(sdk, cap, target_key, extra_config, credentials, wait):
    """Execute a capability directly via the job system."""
    capability = cap['capability']
    config = {}
    if extra_config:
        try:
            config = json.loads(extra_config)
        except json.JSONDecodeError as e:
            error(f'Invalid JSON config: {e}')

    config_str = json.dumps(config) if config else None
    click.echo(f'Queuing {capability} against {target_key}...')
    result = sdk.jobs.add(target_key, [capability], config_str, credentials or None)
    print_json(result)

    if wait:
        _wait_for_job(sdk, target_key, capability)


def _run_via_agent(sdk, cap, target_key):
    """Execute via Marcus AI agent."""
    capability = cap.get('capability', cap.get('name', ''))
    message = f'Run {capability} against {target_key} and analyze the results.'
    click.echo(f'Asking Marcus...')

    try:
        result = sdk.agents.ask(message, mode='agent')
        click.echo(result['response'])
    except Exception as e:
        error(str(e))


def _run_local(sdk, tool_name, target, extra_config):
    """Run a tool locally using the installed binary."""
    from praetorian_cli.runners.local import LocalRunner, get_tool_plugin

    try:
        runner = LocalRunner(tool_name)
    except FileNotFoundError as e:
        error(str(e))

    # Strip Guard key prefix for raw target
    raw_target = target
    if target.startswith('#'):
        parts = target.split('#')
        raw_target = parts[-1] if len(parts) > 3 else parts[2] if len(parts) > 2 else target

    plugin = get_tool_plugin(tool_name)
    args = plugin.build_args(raw_target, extra_config)

    click.echo(f'Running {tool_name} locally against {raw_target}...')
    click.echo(f'Command: {tool_name} {" ".join(args)}')
    click.echo('─' * 60)

    import subprocess
    proc = runner.run_streaming(args)
    output_lines = []
    try:
        for line in proc.stdout:
            click.echo(line, nl=False)
            output_lines.append(line)
        proc.wait(timeout=600)
    except subprocess.TimeoutExpired:
        proc.kill()
        click.echo('\nTimed out (10 min).', err=True)

    stderr = proc.stderr.read() if proc.stderr else ''
    if stderr:
        click.echo(stderr, err=True)

    click.echo('─' * 60)
    click.echo(f'Exit code: {proc.returncode}')

    # Upload output to Guard
    output_text = ''.join(output_lines)
    if output_text.strip():
        try:
            import tempfile, os
            with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False, prefix=f'{tool_name}-') as f:
                f.write(output_text)
                tmp_path = f.name
            guard_path = f'proofs/local/{tool_name}/{raw_target.replace("/", "_")}'
            sdk.files.add(tmp_path, guard_path)
            os.unlink(tmp_path)
            click.echo(f'Output uploaded to Guard: {guard_path}')
        except Exception as e:
            click.echo(f'Failed to upload output: {e}', err=True)


def _wait_for_job(sdk, target_key, capability):
    """Poll for job completion."""
    click.echo('Waiting for job completion...', err=True)
    max_wait = 300
    start_time = time.time()

    while time.time() - start_time < max_wait:
        jobs, _ = sdk.jobs.list(target_key.lstrip('#'))
        matching = [j for j in jobs if capability in j.get('source', '') or capability in j.get('key', '')]
        if matching:
            latest = sorted(matching, key=lambda j: j.get('created', 0), reverse=True)[0]
            status = latest.get('status', '')
            if status.startswith('JP'):
                click.echo('Job completed successfully.', err=True)
                risks, _ = sdk.search.by_source(latest['key'], 'risk')
                if risks:
                    click.echo(f'\nFindings ({len(risks)}):')
                    print_json({'findings': risks})
                else:
                    click.echo('No findings produced.')
                return
            elif status.startswith('JF'):
                click.echo('Job failed.', err=True)
                print_json(latest)
                return
        time.sleep(5)

    click.echo('Timed out waiting for job (5 min).', err=True)
