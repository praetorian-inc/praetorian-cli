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
    'cato':     {'capability': 'cato-agent',     'agent': None,             'target_type': 'risk',
                 'description': 'Finding validation & triage'},
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
def tool(sdk, tool_name, target, extra_config, credential, wait, use_agent):
    """ Execute a named security tool against a target

    TARGET can be a Guard entity key (#asset#...) or a friendly name
    (domain, IP, URL). The CLI will resolve it to the correct entity.

    \b
    Example usages:
        guard run tool portscan example.com
        guard run tool portscan "#asset#example.com#1.2.3.4"
        guard run tool brutus 10.0.1.5 --wait
        guard run tool nuclei example.com --config '{"templates":"cves"}'
        guard run tool titus github.com/org/repo
        guard run tool asset-analyzer example.com --ask
    """
    tool_name = tool_name.lower()
    alias = TOOL_ALIASES.get(tool_name)
    if not alias:
        available = ', '.join(sorted(k for k in TOOL_ALIASES if k != 'secrets'))
        error(f'Unknown tool: {tool_name}. Available: {available}')

    # Resolve target to a Guard key
    target_key, warning = resolve_target(sdk, target, alias['target_type'])
    if not target_key:
        error(warning)
    if warning:
        click.echo(warning, err=True)

    if alias.get('agent') and (use_agent or not alias.get('capability')):
        _run_via_agent(sdk, alias, target_key)
    else:
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
