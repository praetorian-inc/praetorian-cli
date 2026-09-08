import json
from datetime import datetime

from rich.box import MINIMAL
from rich.prompt import Confirm, Prompt
from rich.table import Table

from praetorian_cli.sdk.entities.capabilities import (
    capability_name,
    normalize_capabilities_response,
)
from ..constants import DEFAULT_COLORS
from ..utils import agent_display_id, format_job_status, format_timestamp, is_v2_agent
from .job_helpers import extract_target_type


def _endpoint_capabilities(menu):
    sdk_capabilities = getattr(getattr(menu, 'sdk', None), 'capabilities', None)
    if sdk_capabilities is None or not hasattr(sdk_capabilities, 'list'):
        return []

    selected_agent = getattr(menu, 'selected_agent', None)
    endpoint_kind = getattr(selected_agent, 'kind', '')
    if not endpoint_kind:
        raise RuntimeError('selected endpoint does not report an endpoint kind')

    cache_key = (agent_display_id(selected_agent), endpoint_kind)
    cached = getattr(menu, '_aegis_v2_endpoint_capabilities_cache', None)
    if isinstance(cached, dict) and cached.get('key') == cache_key:
        return list(cached.get('capabilities', []))

    try:
        result = sdk_capabilities.list(endpoint_kind=endpoint_kind)
    except Exception as exc:
        raise RuntimeError(f'failed to load endpoint capabilities: {exc}') from exc

    capabilities = [cap for cap in normalize_capabilities_response(result) if _capability_name(cap)]
    capabilities = sorted(capabilities, key=lambda cap: _capability_name(cap).lower())
    setattr(menu, '_aegis_v2_endpoint_capabilities_cache', {
        'key': cache_key,
        'capabilities': capabilities,
    })
    return list(capabilities)


def _capability_name(capability_info):
    return capability_name(capability_info)


def _capability_names(capabilities):
    names = []
    for capability in capabilities:
        name = _capability_name(capability)
        if name:
            names.append(name)
    return names


def show_job_help(menu):
    help_text = f"""
  Aegis v2 Job Commands

  job list                  List recent jobs for selected v2 endpoint
  job run <capability>      Run a v2 capability through the selected endpoint
  job capabilities          List supported v2 capabilities (alias: caps)
                           [--details] Show full descriptions

  Capabilities are loaded from Guard at runtime.

  Examples:
    job capabilities
    job run <capability> <existing-asset-or-key> --yes
    job run <capability> --key "#port#example.com#1.2.3.4#443#tcp"

  Note: asset targets must already exist in Guard.
"""
    menu.console.print(help_text)
    menu.pause()


def list_jobs(menu):
    colors = getattr(menu, 'colors', DEFAULT_COLORS)
    endpoint_id = agent_display_id(menu.selected_agent)
    try:
        jobs, _ = menu.sdk.jobs.list(pages=1)
        endpoint_jobs = [job for job in jobs if _job_endpoint_id(job) == endpoint_id]
        if not endpoint_jobs:
            menu.console.print(f"\n  No recent jobs found for endpoint {endpoint_id}\n")
            menu.pause()
            return
        show_jobs_table(menu, endpoint_jobs, f"  Recent Jobs for endpoint {endpoint_id}")
        menu.pause()
    except Exception as e:
        menu.console.print(f"[{colors['error']}]Error listing endpoint jobs: {e}[/{colors['error']}]")
        menu.pause()


def run_job(menu, args):
    colors = getattr(menu, 'colors', DEFAULT_COLORS)
    endpoint_id = agent_display_id(menu.selected_agent)

    try:
        parsed = _parse_run_args(args)
    except ValueError as e:
        menu.console.print(f"[{colors['error']}]Error: {e}[/{colors['error']}]")
        _print_run_help(menu)
        return

    if parsed['help']:
        _print_run_help(menu)
        return

    try:
        capabilities = _endpoint_capabilities(menu)
    except RuntimeError as e:
        menu.console.print(f"[{colors['error']}]Error: {e}[/{colors['error']}]")
        menu.pause()
        return

    if not capabilities:
        menu.console.print(f"  [{colors['warning']}]No Aegis v2 endpoint capabilities returned by Guard.[/{colors['warning']}]")
        menu.pause()
        return

    capability = parsed['capability'].lower() if parsed['capability'] else _prompt_capability(menu, capabilities)
    capability_info = _capability_info(capability, capabilities)
    if not capability_info:
        menu.console.print(
            f"  [{colors['error']}]Invalid Aegis v2 capability: '{capability}'[/{colors['error']}]"
        )
        menu.console.print("  Use 'job capabilities' to see Guard-reported endpoint capabilities.")
        menu.pause()
        return

    capability = _capability_name(capability_info)

    try:
        config = _job_config(parsed['config'], endpoint_id)
    except ValueError as e:
        menu.console.print(f"[{colors['error']}]Error: {e}[/{colors['error']}]")
        menu.pause()
        return

    target_key, target_display = _target_key(
        menu,
        capability_info,
        parsed['target'],
        parsed['target_key'],
    )
    if not target_key:
        menu.pause()
        return

    if not parsed['yes']:
        if not Confirm.ask(f"\n  Run '{capability}' on {target_display} via endpoint {endpoint_id}?"):
            menu.console.print('  Cancelled\n')
            menu.pause()
            return

    try:
        jobs = menu.sdk.jobs.add(target_key, [capability], json.dumps(config))
        if jobs:
            _print_queued_job(menu, jobs[0] if isinstance(jobs, list) else jobs, capability, target_display, endpoint_id)
        else:
            menu.console.print(f"\n[{colors['error']}]Error: No job returned from API[/{colors['error']}]")
    except Exception as e:
        menu.console.print(f"\n[{colors['error']}]Job execution error: {e}[/{colors['error']}]")

    menu.console.print()
    menu.pause()


def list_capabilities(menu, args):
    show_details = '--details' in args or '-d' in args
    colors = getattr(menu, 'colors', DEFAULT_COLORS)

    try:
        capabilities = _endpoint_capabilities(menu)
    except RuntimeError as e:
        menu.console.print(f"[{colors['error']}]Error: {e}[/{colors['error']}]")
        menu.pause()
        return

    if not capabilities:
        menu.console.print(f"  [{colors['warning']}]No Aegis v2 endpoint capabilities returned by Guard.[/{colors['warning']}]")
        menu.pause()
        return

    capabilities_table = Table(
        show_header=True,
        header_style=f"bold {colors['primary']}",
        border_style=colors['dim'],
        box=MINIMAL,
        show_lines=False,
        padding=(0, 2),
        pad_edge=False,
    )
    capabilities_table.add_column('CAPABILITY', style=f"bold {colors['success']}", min_width=16, no_wrap=True)
    capabilities_table.add_column('TARGET', style=f"{colors['dim']}", width=10, no_wrap=True)
    capabilities_table.add_column('DESCRIPTION', style='white', no_wrap=False)

    for info in capabilities:
        name = _capability_name(info)
        description = info.get('description') or info.get('Description') or 'No description available'
        if not show_details and len(description) > 80:
            description = description[:80] + '...'
        capabilities_table.add_row(name, extract_target_type(info), description)

    menu.console.print()
    title = '  Aegis v2 Endpoint Capabilities'
    title += ' (Detailed)' if show_details else ' (use --details for full descriptions)'
    menu.console.print(title)
    menu.console.print()
    menu.console.print(capabilities_table)
    menu.console.print()
    menu.pause()


def complete(menu, text, tokens):
    if not is_v2_agent(getattr(menu, 'selected_agent', None)):
        return []
    if len(tokens) < 2 or tokens[1] != 'run':
        return []
    if text.startswith('-'):
        opts = ['--target', '--key', '--target-key', '--asset-key', '--config', '--yes', '--help', '-t', '-k', '-y']
        return [option for option in opts if option.startswith(text)]
    if len(tokens) <= 3:
        try:
            capability_names = _capability_names(_endpoint_capabilities(menu))
        except RuntimeError:
            return []
        return [capability for capability in capability_names if capability.startswith(text)]
    return []


def _capability_info(capability, capabilities):
    requested = (capability or '').lower()
    for info in capabilities:
        if _capability_name(info).lower() == requested:
            return info
    return None


def _print_run_help(menu):
    menu.console.print(f"""
  Aegis v2 Job Run

  Usage:
    job run <capability> [target] [--yes]
    job run <capability> --target <target> [--yes]
    job run <capability> --key <target-key> [--yes]
    job run <capability> --config '{{"param":"value"}}' [--yes]

  Capabilities are loaded from Guard at runtime. Use 'job capabilities' to list them.

  For asset-targeted capabilities, TARGET can be a #asset# key or an existing asset value.
  The CLI does not create assets here because asset writes enqueue normal jobs.
  Other target types require --key for the target entity.
""")
    menu.pause()


def _parse_run_args(args):
    parsed = {
        'capability': None,
        'target': None,
        'target_key': None,
        'config': None,
        'yes': False,
        'help': False,
    }
    positional = []
    i = 0
    while i < len(args):
        arg = args[i]
        if arg in ('-h', '--help'):
            parsed['help'] = True
            i += 1
        elif arg in ('-t', '--target'):
            if i + 1 >= len(args):
                raise ValueError(f'{arg} requires a target')
            parsed['target'] = args[i + 1]
            i += 2
        elif arg in ('-k', '--key', '--target-key', '--asset-key'):
            if i + 1 >= len(args):
                raise ValueError(f'{arg} requires a target key')
            parsed['target_key'] = args[i + 1]
            i += 2
        elif arg == '--config':
            if i + 1 >= len(args):
                raise ValueError('--config requires a JSON value')
            parsed['config'] = args[i + 1]
            i += 2
        elif arg.startswith('--config='):
            parsed['config'] = arg.split('=', 1)[1]
            i += 1
        elif arg in ('-y', '--yes'):
            parsed['yes'] = True
            i += 1
        elif arg.startswith('-'):
            raise ValueError(f'Unknown option: {arg}')
        else:
            positional.append(arg)
            i += 1

    if positional:
        parsed['capability'] = positional[0]
    if len(positional) > 1:
        if parsed['target'] or parsed['target_key']:
            raise ValueError('Target specified more than once')
        parsed['target'] = positional[1]
    if len(positional) > 2:
        raise ValueError('Too many positional arguments')

    return parsed


def _job_config(config_json, endpoint_id):
    config = {}
    if config_json:
        try:
            config = json.loads(config_json)
        except json.JSONDecodeError as e:
            raise ValueError(f'Invalid JSON in --config: {e}')
        if not isinstance(config, dict):
            raise ValueError('--config must be a JSON object')

    legacy_keys = {'aegis', 'client_id'} & set(config)
    if legacy_keys:
        joined = ', '.join(sorted(legacy_keys))
        raise ValueError(f'Aegis v2 jobs do not support legacy config keys: {joined}')

    configured_endpoint = config.get('endpoint_agent_id')
    if configured_endpoint and configured_endpoint != endpoint_id:
        raise ValueError('endpoint_agent_id must match the selected Aegis v2 endpoint')
    config['endpoint_agent_id'] = endpoint_id
    return config


def _prompt_capability(menu, capabilities):
    names = _capability_names(capabilities)
    if not names:
        return None
    capability = Prompt.ask(
        '  Capability',
        choices=names,
        default=names[0],
    )
    return capability.strip().lower() if capability else None


def _target_key(menu, capability_info, target, target_key):
    colors = getattr(menu, 'colors', DEFAULT_COLORS)
    capability = _capability_name(capability_info)
    target_type = extract_target_type(capability_info)
    if target_key:
        return target_key, target_key

    target = target.strip() if isinstance(target, str) else target
    if target and target.startswith('#'):
        return target, target

    if target_type != 'asset':
        if not target:
            target = Prompt.ask(f'  {target_type} target key')
        if target and target.startswith('#'):
            return target, target
        menu.console.print(
            f"  [{colors['error']}]Aegis v2 {capability} requires a {target_type} target key.[/{colors['error']}]"
        )
        menu.console.print('  Use --key with the target entity key.')
        return None, None

    if not target:
        target = Prompt.ask('  Existing target asset value or #asset# key')
    if not target:
        menu.console.print('  Cancelled')
        return None, None
    target = target.strip()
    if target.startswith('#'):
        return target, target

    asset_key = _existing_asset_key(menu, target)
    if asset_key:
        return asset_key, target

    menu.console.print(f"  [{colors['error']}]No existing asset found for {target}.[/{colors['error']}]")
    menu.console.print('  Aegis v2 job run will not create assets automatically; asset writes enqueue normal jobs.')
    menu.console.print(f'  Add or approve the asset first, then rerun: guard add asset --group {target} --surface internal')
    return None, None


def _existing_asset_key(menu, target):
    candidate_key = f'#asset#{target}#{target}'
    try:
        asset = menu.sdk.assets.get(candidate_key)
    except Exception:
        return None
    if not asset:
        return None
    return asset.get('key') or candidate_key


def _job_details_config(job):
    config = job.get('config') or {}
    if isinstance(config, str):
        try:
            return json.loads(config)
        except json.JSONDecodeError:
            return {}
    return config if isinstance(config, dict) else {}


def _job_endpoint_id(job):
    return _job_details_config(job).get('endpoint_agent_id')


def _job_capability(job):
    capabilities = job.get('capabilities')
    if isinstance(capabilities, list) and capabilities:
        return capabilities[0]
    key_parts = (job.get('key') or '').split('#')
    if len(key_parts) >= 5:
        return key_parts[-2]
    return 'unknown'


def show_jobs_table(menu, jobs, title):
    colors = getattr(menu, 'colors', DEFAULT_COLORS)
    sorted_jobs = sorted(jobs, key=_job_created_sort_value, reverse=True)

    jobs_table = Table(
        show_header=True,
        header_style=f"bold {colors['primary']}",
        border_style=colors['dim'],
        box=MINIMAL,
        show_lines=False,
        padding=(0, 2),
        pad_edge=False,
    )
    jobs_table.add_column('JOB ID', style=f"bold {colors['accent']}", width=12, no_wrap=True)
    jobs_table.add_column('CAPABILITY', style='white', min_width=20, no_wrap=True)
    jobs_table.add_column('STATUS', width=10, justify='center', no_wrap=True)
    jobs_table.add_column('CREATED', style=f"{colors['dim']}", width=12, justify='right', no_wrap=True)

    menu.console.print()
    menu.console.print(title)
    menu.console.print()
    for job in sorted_jobs[:10]:
        status = job.get('status', 'unknown')
        job_id = job.get('key', '').split('#')[-1][:10]
        created = job.get('created', 0)
        jobs_table.add_row(
            job_id,
            _job_capability(job),
            format_job_status(status, colors),
            format_timestamp(created),
        )
    menu.console.print(jobs_table)
    menu.console.print()


def _job_created_sort_value(job):
    created = job.get('created')
    if isinstance(created, (int, float)):
        return float(created)
    if isinstance(created, str):
        try:
            return datetime.fromisoformat(created.replace('Z', '+00:00')).timestamp()
        except (TypeError, ValueError, OSError, OverflowError):
            return 0.0
    return 0.0


def _print_queued_job(menu, job, capability, target_display, endpoint_id):
    colors = getattr(menu, 'colors', DEFAULT_COLORS)
    job_key = job.get('key', '')
    status = job.get('status', 'unknown')
    job_id = job_key.split('#')[-1] if job_key else 'unknown'

    menu.console.print(f"\n[{colors['success']}]✓ Job queued successfully[/{colors['success']}]")
    menu.console.print(f'  Job ID: {job_id}')
    menu.console.print(f'  Job Key: {job_key}')
    menu.console.print(f'  Capability: {capability}')
    menu.console.print(f'  Target: {target_display}')
    menu.console.print(f'  Endpoint ID: {endpoint_id}')
    menu.console.print(f'  Status: {status}')
