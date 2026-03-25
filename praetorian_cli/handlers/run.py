import json
import time

import click

from praetorian_cli.handlers.chariot import chariot
from praetorian_cli.handlers.cli_decorators import cli_handler
from praetorian_cli.handlers.utils import print_json, error


# Valid target types each tool can run against
VALID_TARGETS = {
    'asset':          {'asset'},
    'port':           {'port'},
    'webpage':        {'webpage'},
    'webapplication': {'webapplication'},
    'repository':     {'repository', 'asset'},  # repos are assets with type=repository
    'risk':           {'risk'},
    'addomain':       {'addomain'},
    'preseed':        {'preseed'},
    'awsresource':    {'awsresource', 'asset'},
    'azureresource':  {'azureresource', 'asset'},
    'noinput':        set(),  # no target needed
}

# Named tool aliases — operator-friendly names mapped to real backend capability names
TOOL_ALIASES = {
    # ── Named Agents (Praetorian Roman theme) ────────────────────
    'asset-analyzer': {'capability': 'asset-analyzer', 'agent': 'asset-analyzer', 'target_type': 'asset',
                 'description': 'Deep-dive reconnaissance & risk mapping'},
    'brutus':   {'capability': 'brutus',         'agent': 'brutus-agent',   'target_type': 'port',
                 'description': 'Credential attacks (SSH, RDP, FTP, SMB)',
                 'default_config': {'manual': 'true'}},
    'julius':   {'capability': 'julius',         'agent': 'julius-agent',   'target_type': 'port',
                 'description': 'LLM/AI service fingerprinting'},
    'augustus':  {'capability': 'augustus',        'agent': 'augustus-agent',  'target_type': 'webpage',
                 'description': 'LLM jailbreak & prompt injection attacks'},
    'aurelius': {'capability': 'aurelian-aws-list-all', 'agent': 'aurelian-agent', 'target_type': 'asset',
                 'description': 'Cloud infrastructure discovery (AWS/Azure/GCP)'},
    'trajan':   {'capability': 'Trajan',         'agent': 'trajan-agent',   'target_type': 'repository',
                 'description': 'CI/CD pipeline security scanning'},
    'priscus':  {'capability': 'priscus-agent',  'agent': None,             'target_type': 'risk',
                 'description': 'Remediation retesting'},
    'seneca':   {'capability': 'seneca-agent',   'agent': None,             'target_type': 'risk',
                 'description': 'CVE research & exploit intelligence'},
    'titus':    {'capability': 'secrets',        'agent': 'titus-agent',    'target_type': 'repository',
                 'description': 'Secret scanning & credential leak detection'},

    # ── Direct Capabilities ──────────────────────────────────────
    'nuclei':   {'capability': 'nuclei',         'agent': None,             'target_type': 'port',
                 'description': 'Vulnerability scanner templates'},
    'portscan': {'capability': 'portscan',       'agent': None,             'target_type': 'asset',
                 'description': 'Scan for open ports'},
    'subdomain':{'capability': 'subdomain',      'agent': None,             'target_type': 'asset',
                 'description': 'Subdomain enumeration'},
    'crawler':  {'capability': 'crawler',        'agent': None,             'target_type': 'webapplication',
                 'description': 'Web application crawling'},
    'whois':    {'capability': 'whois',          'agent': None,             'target_type': 'asset',
                 'description': 'Domain registration lookup'},
    'secrets':  {'capability': 'secrets',        'agent': 'titus-agent',    'target_type': 'repository',
                 'description': 'Secret scanning (alias for titus)'},
    'gowitness':{'capability': 'gowitness',      'agent': None,             'target_type': 'webpage',
                 'description': 'Web page screenshot capture'},
    'constantine':{'capability': 'constantine',  'agent': None,             'target_type': 'repository',
                 'description': 'Repository security analysis'},
    'gato':     {'capability': 'gato',           'agent': None,             'target_type': 'repository',
                 'description': 'GitHub Actions security scanning'},
    'login-detection': {'capability': 'login-detection', 'agent': None,     'target_type': 'webpage',
                 'description': 'Detect login pages on web applications'},
    'webpage-secrets': {'capability': 'webpage-secrets', 'agent': None,     'target_type': 'webpage',
                 'description': 'Scan web pages for leaked secrets'},
    'ssh':      {'capability': 'ssh',            'agent': None,             'target_type': 'port',
                 'description': 'SSH key and configuration analysis'},
    'resolver': {'capability': 'resolver',       'agent': None,             'target_type': 'asset',
                 'description': 'DNS resolution'},
    'vespasian':{'capability': 'vespasian',      'agent': None,             'target_type': 'webapplication',
                 'description': 'Web application security testing'},
}


def resolve_target(sdk, target_input, expected_type):
    """Resolve a friendly target (domain, IP, URL, etc.) to a Guard entity key.

    If target_input already looks like a Guard key (#asset#..., #port#..., etc.),
    return it as-is. Otherwise, search Guard for a matching entity.

    Returns (key, error_message) tuple.
    """
    # Already a Guard key
    if target_input.startswith('#'):
        return _validate_key_type(target_input, expected_type)

    # Try to resolve by searching
    valid_types = VALID_TARGETS.get(expected_type, {expected_type})

    for vtype in valid_types:
        prefix = f'#{vtype}#'
        try:
            # Search by key prefix containing the input
            results, _ = sdk.search.by_key_prefix(f'{prefix}{target_input}', pages=1)
            if results:
                if len(results) == 1:
                    return results[0]['key'], None
                # Multiple matches — try exact dns/name match first
                for r in results:
                    dns = r.get('dns', '')
                    name = r.get('name', '')
                    if dns == target_input or name == target_input:
                        return r['key'], None
                # Return first match with a hint
                return results[0]['key'], None
        except Exception:
            pass

    # Try additional search strategies based on target type
    if expected_type in ('asset', 'repository'):
        # Try dns: search
        for field in ('dns', 'name'):
            try:
                results, _ = sdk.search.by_term(f'{field}:{target_input}', expected_type, pages=1)
                if results:
                    return results[0]['key'], None
            except Exception:
                pass

    if expected_type == 'port':
        # Try searching for ports by IP or service — name:target_input
        try:
            results, _ = sdk.search.by_term(f'name:{target_input}', 'port', pages=1)
            if results:
                return results[0]['key'], None
        except Exception:
            pass

    if expected_type == 'risk':
        try:
            results, _ = sdk.search.by_term(f'name:{target_input}', 'risk', pages=1)
            if results:
                return results[0]['key'], None
        except Exception:
            pass

    if expected_type == 'webpage':
        try:
            results, _ = sdk.search.by_key_prefix(f'#webpage#', pages=1)
            matching = [r for r in results if target_input in r.get('key', '') or target_input in r.get('name', '')]
            if matching:
                return matching[0]['key'], None
        except Exception:
            pass

    return None, f'Could not resolve "{target_input}" to a {expected_type}. Use a full Guard key (#asset#...) or check the entity exists.'


def _validate_key_type(key, expected_type):
    """Check that a Guard key matches the expected target type."""
    valid_types = VALID_TARGETS.get(expected_type, {expected_type})
    key_type = key.split('#')[1] if key.startswith('#') and '#' in key[1:] else ''

    if key_type in valid_types:
        return key, None

    return key, f'Warning: {key} is a {key_type}, but {expected_type} expected. Proceeding anyway.'


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
@click.option('-c', '--config', 'extra_config', default='', help='Extra JSON config to merge (e.g., \'{"manual":"true"}\')')
@click.option('--credential', multiple=True, help='Credential ID(s) to use')
@click.option('--wait', is_flag=True, default=False, help='Wait for job completion and show results')
@click.option('--ask', 'use_agent', is_flag=True, default=False, help='Run via Marcus AI agent instead of direct job (enables analysis)')
@click.option('--local', is_flag=True, default=False, help='Run locally using installed binary (default if binary exists)')
@click.option('--remote', is_flag=True, default=False, help='Force remote job execution on Guard backend')
def tool(sdk, tool_name, target, extra_config, credential, wait, use_agent, local, remote):
    """ Execute a named security tool against a target

    By default, runs LOCALLY if the binary is installed, otherwise schedules
    a remote job on the Guard backend. Use --local or --remote to force.

    \b
    Example usages:
        guard run tool brutus 10.0.1.5                 (local if installed)
        guard run tool brutus 10.0.1.5 --remote        (force backend job)
        guard run tool nuclei example.com --local       (force local binary)
        guard run tool titus github.com/org/repo
        guard run tool asset-analyzer example.com --ask
    """
    from praetorian_cli.runners.local import is_installed as _is_installed

    tool_name = tool_name.lower()
    alias = TOOL_ALIASES.get(tool_name)
    if not alias:
        available = ', '.join(sorted(k for k in TOOL_ALIASES if k != 'secrets'))
        error(f'Unknown tool: {tool_name}. Available: {available}')

    # Decide: local vs remote
    run_local = False
    if local:
        run_local = True
    elif remote or use_agent:
        run_local = False
    elif _is_installed(tool_name):
        run_local = True  # Default to local if binary exists

    if run_local:
        _run_local(sdk, tool_name, target, extra_config)
    elif alias.get('agent') and (use_agent or not alias.get('capability')):
        # Resolve for remote
        target_key, warning = resolve_target(sdk, target, alias['target_type'])
        if not target_key:
            error(warning)
        if warning:
            click.echo(warning, err=True)
        _run_via_agent(sdk, alias, target_key)
    else:
        target_key, warning = resolve_target(sdk, target, alias['target_type'])
        if not target_key:
            error(warning)
        if warning:
            click.echo(warning, err=True)
        _run_direct(sdk, alias, target_key, extra_config, list(credential), wait)


@run.command('list')
@cli_handler
def list_tools(sdk):
    """ List available security tools and their descriptions

    \b
    Example usage:
        guard run list
    """
    agents = {k: v for k, v in TOOL_ALIASES.items() if v.get('agent') and k != 'secrets'}
    caps = {k: v for k, v in TOOL_ALIASES.items() if not v.get('agent') and k != 'secrets'}

    click.echo(f'\n{"Agent":<16} {"Description"}')
    click.echo(f'{"─"*16} {"─"*50}')
    for name, info in sorted(agents.items()):
        click.echo(f'{name:<16} {info["description"]}')

    click.echo(f'\n{"Capability":<16} {"Target":<12} {"Description"}')
    click.echo(f'{"─"*16} {"─"*12} {"─"*50}')
    for name, info in sorted(caps.items()):
        click.echo(f'{name:<16} {info["target_type"]:<12} {info["description"]}')


@run.command('capabilities')
@cli_handler
@click.option('-n', '--name', default='', help='Filter by capability name')
@click.option('-t', '--target', default='', help='Filter by target type (asset, port, webpage, repository)')
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
        guard run install nuclei --force
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
    """ List locally installed capability binaries

    \b
    Example usage:
        guard run installed
    """
    from praetorian_cli.runners.local import list_installed, INSTALLABLE_TOOLS

    inst = list_installed()
    click.echo(f'\n{"Tool":<16} {"Status":<12} {"Path"}')
    click.echo(f'{"─"*16} {"─"*12} {"─"*50}')
    for name in sorted(INSTALLABLE_TOOLS):
        if name in inst:
            click.echo(f'{name:<16} {"installed":<12} {inst[name]}')
        else:
            click.echo(f'{name:<16} {"—":<12}')


def _run_local(sdk, tool_name, target, extra_config):
    """Run a tool locally using the installed binary and upload results to Guard."""
    from praetorian_cli.runners.local import LocalRunner

    try:
        runner = LocalRunner(tool_name)
    except FileNotFoundError as e:
        error(str(e))

    # Strip Guard key prefix — local tools want raw targets (domain, IP, URL, path)
    raw_target = target
    if target.startswith('#'):
        parts = target.split('#')
        # Key format: #type#group#identifier — take identifier or group
        raw_target = parts[-1] if len(parts) > 3 else parts[2] if len(parts) > 2 else target

    # Build args based on tool
    args = _build_local_args(tool_name, raw_target, extra_config)

    click.echo(f'Running {tool_name} locally against {raw_target}...')
    click.echo(f'Binary: {runner.binary_path}')
    click.echo(f'Command: {tool_name} {" ".join(args)}')
    click.echo('─' * 60)

    # Run with live output
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
    exit_code = proc.returncode
    click.echo(f'Exit code: {exit_code}')

    # Upload output to Guard as a file
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


def _build_local_args(tool_name, target, extra_config):
    """Build CLI arguments for a local tool run."""
    config = {}
    if extra_config:
        try:
            config = json.loads(extra_config)
        except json.JSONDecodeError:
            pass

    # Tool-specific argument patterns
    if tool_name == 'brutus':
        args = ['-t', target]
        if config.get('usernames'):
            args.extend(['-u', config['usernames']])
        if config.get('passwords'):
            args.extend(['-p', config['passwords']])
        return args
    elif tool_name == 'nuclei':
        args = ['-u', target, '-jsonl']
        if config.get('templates'):
            args.extend(['-t', config['templates']])
        return args
    elif tool_name == 'titus':
        args = ['scan', target]
        if config.get('validation') == 'true':
            args.append('--validate')
        return args
    elif tool_name == 'trajan':
        return ['scan', target]
    elif tool_name == 'julius':
        return ['-t', target]
    elif tool_name == 'augustus':
        return ['scan', '-t', target]
    elif tool_name == 'cato':
        return ['scan', '-u', target]
    elif tool_name == 'nerva':
        return ['-t', target]
    elif tool_name == 'vespasian':
        return ['discover', target]
    elif tool_name == 'gato':
        return ['enumerate', '-t', target]
    elif tool_name == 'aurelian':
        return ['scan']
    elif tool_name == 'pius':
        return ['discover', target]
    elif tool_name == 'florian':
        return ['scan', '-u', target]
    elif tool_name == 'caligula':
        return ['scan', target]
    elif tool_name == 'hadrian':
        return ['scan', '-u', target]
    elif tool_name == 'nero':
        return ['-t', target]
    elif tool_name == 'constantine':
        return ['scan', target]
    else:
        # Generic: pass target as first arg
        return [target]


def _run_direct(sdk, alias, target_key, extra_config, credentials, wait):
    """Execute a capability directly via the job system."""
    capability = alias['capability']

    config = dict(alias.get('default_config', {}))
    if extra_config:
        try:
            config.update(json.loads(extra_config))
        except json.JSONDecodeError as e:
            error(f'Invalid JSON config: {e}')

    config_str = json.dumps(config) if config else None
    click.echo(f'Queuing {capability} against {target_key}...')

    result = sdk.jobs.add(target_key, [capability], config_str, credentials or None)
    print_json(result)

    if wait:
        _wait_for_job(sdk, target_key, capability)


def _run_via_agent(sdk, alias, target_key):
    """Execute via Marcus AI agent for richer analysis."""
    agent_name = alias['agent']
    capability = alias.get('capability')

    if capability:
        message = f'Run {capability} against {target_key} and analyze the results.'
    else:
        message = f'Analyze {target_key} thoroughly using {agent_name}.'

    click.echo(f'Asking Marcus to run {agent_name}...')

    url = sdk.url('/planner')
    payload = {'message': message, 'mode': 'agent'}

    response = sdk.chariot_request('POST', url, json=payload)
    if not response.ok:
        error(f'API error: {response.status_code} - {response.text}')

    result = response.json()
    conversation_id = result.get('conversation', {}).get('uuid')

    last_key = ''
    max_wait = 180
    start_time = time.time()

    while time.time() - start_time < max_wait:
        messages, _ = sdk.search.by_key_prefix(f'#message#{conversation_id}#', user=True)
        new_msgs = sorted(
            [m for m in messages if m.get('key', '') > last_key],
            key=lambda x: x.get('key', '')
        )

        for msg in new_msgs:
            role = msg.get('role', '')
            content = msg.get('content', '')
            last_key = msg.get('key', '')

            if role == 'chariot':
                click.echo(content)
                return
            elif role == 'tool call':
                click.echo('Executing...', err=True, nl=False)
            elif role == 'tool response':
                click.echo(' done.', err=True)

        time.sleep(2)

    error('Timed out waiting for agent response (3 min)')


def _wait_for_job(sdk, target_key, capability):
    """Poll for job completion and show results."""
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
                click.echo(f'Job failed.', err=True)
                print_json(latest)
                return

        time.sleep(5)

    click.echo('Timed out waiting for job (5 min).', err=True)
