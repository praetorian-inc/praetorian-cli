import json

import click
from praetorian_cli.handlers.chariot import chariot
from praetorian_cli.handlers.cli_decorators import cli_handler, praetorian_only
from praetorian_cli.handlers.utils import print_json


@chariot.group(invoke_without_command=True)
@cli_handler
@click.pass_context
def aegis(ctx, sdk):
    """Aegis management commands"""
    if ctx.invoked_subcommand is None:
        # No subcommand was invoked, run the default interactive interface
        from praetorian_cli.ui.aegis.menu import run_aegis_menu
        run_aegis_menu(sdk)


# Add the shared commands to the CLI group
# Each shared command gets wrapped to inject the CLI context

@aegis.command('list')
@cli_handler
@click.option('--details', is_flag=True, help='Show detailed agent information')
@click.option('--filter', help='Filter agents by hostname or other properties')
@click.pass_context
def list_agents(ctx, sdk, details, filter):
    """List Aegis agents with optional details"""
    click.echo(sdk.aegis.format_agents_list(details=details, filter_text=filter))


@aegis.command('ssh')
@cli_handler
@click.argument('client_id', required=True)
@click.option('-u', '--user', help='SSH username (prepends user@ to hostname)')
@click.argument('args', nargs=-1)
@click.pass_context
def ssh(ctx, sdk, client_id, user, args):
    """Connect to an Aegis agent via SSH.

    Pass native ssh flags after client_id; they are forwarded to ssh.

    Common options (forwarded to ssh):
      -L [bind_address:]port:host:hostport   Local port forward (repeatable)
      -R [bind_address:]port:host:hostport   Remote port forward (repeatable)
      -D [bind_address:]port                 Dynamic SOCKS proxy
      -i IDENTITY_FILE                       Identity (private key) file
      -l USER                                Remote username (alternative to -u/--user)
      -o OPTION=VALUE                        Extra ssh config option
      -p PORT                                SSH port
      -v/-vv/-vvv                            Verbose output
    """
    agent = sdk.aegis.get_by_client_id(client_id)
    if not agent:
        click.echo(f"Agent not found: {client_id}", err=True)
        return

    options = list(args)
    sdk.aegis.ssh_to_agent(agent=agent, options=options, user=user, display_info=True)


@aegis.command('cp')
@cli_handler
@click.argument('client_id', required=True)
@click.argument('paths', nargs=2)
@click.option('-u', '--user', help='SSH username')
@click.option('-i', '--identity', 'key', help='Identity (private key) file')
@click.option('--no-rsync', is_flag=True, help='Use scp instead of rsync')
@click.pass_context
def cp(ctx, sdk, client_id, paths, user, key, no_rsync):
    """Copy files to/from an Aegis agent.

    Use a ':' prefix to denote remote paths:

    \b
      Upload:   guard aegis cp <id> ./local_file :/remote/path/
      Download: guard aegis cp <id> :/remote/file ./local_dir/
    """
    src, dst = paths

    src_remote = src.startswith(':')
    dst_remote = dst.startswith(':')

    if src_remote and dst_remote:
        click.echo("Error: both paths cannot be remote", err=True)
        return
    if not src_remote and not dst_remote:
        click.echo("Error: one path must be remote (prefix with ':')", err=True)
        return

    agent = sdk.aegis.get_by_client_id(client_id)
    if not agent:
        click.echo(f"Agent not found: {client_id}", err=True)
        return

    if src_remote:
        direction = 'download'
        remote_path = src[1:]
        local_path = dst
    else:
        direction = 'upload'
        local_path = src
        remote_path = dst[1:]

    ssh_options = []
    if key:
        ssh_options.extend(['-i', key])

    try:
        rc = sdk.aegis.copy_to_agent(
            agent=agent,
            local_path=local_path,
            remote_path=remote_path,
            direction=direction,
            user=user,
            ssh_options=ssh_options,
            display_info=True,
            use_rsync=not no_rsync,
        )
        if rc != 0:
            click.echo(f"Copy failed with exit code {rc}", err=True)
    except Exception as e:
        click.echo(f"Error: {e}", err=True)


@aegis.command('job')
@cli_handler
@click.option('-c', '--capability', 'capabilities', multiple=True, help='Capability to run (e.g., windows-smb-snaffler)')
@click.option('--config', help='JSON configuration string for the job')
@click.argument('client_id', required=True)
@click.pass_context
def job(ctx, sdk, capabilities, config, client_id):
    """Run a job on an Aegis agent"""
    agent = sdk.aegis.get_by_client_id(client_id)
    if not agent:
        click.echo(f"Agent not found: {client_id}", err=True)
        return
    
    try:
        result = sdk.aegis.run_job(
            agent,
            list(capabilities) if capabilities else None,
            config
        )

        if 'capabilities' in result:
            click.echo("Available capabilities:")
            for cap in result['capabilities']:
                name = cap.get('name', 'unknown')
                desc = cap.get('description', '')[:50]
                click.echo(f"  {name:<25} {desc}")
        elif result.get('success'):
            click.echo("✓ Job queued successfully")
            click.echo(f"  Job ID: {result.get('job_id', 'unknown')}")
            click.echo(f"  Status: {result.get('status', 'unknown')}")
        else:
            click.echo("Error: Unknown error", err=True)
    except Exception as e:
        click.echo(f"Error: {e}", err=True)


@aegis.command('info')
@cli_handler
@click.argument('client_id', required=True)
@click.pass_context
def info(ctx, sdk, client_id):
    """Show detailed information for an agent"""
    agent = sdk.aegis.get_by_client_id(client_id)
    if not agent:
        click.echo(f"Agent not found: {client_id}", err=True)
        return
    
    click.echo(agent.to_detailed_string())


# --- Management commands (ST-9) ---

@aegis.command('installer')
@cli_handler
@praetorian_only
@click.option('--flavor', required=True,
              type=click.Choice(['deb', 'rpm', 'msi']),
              help='Installer package format')
@click.option('--proxy', default=None, help='Proxy URL to embed in installer config')
def installer(sdk, flavor, proxy):
    """ Download an Aegis installer package

    \b
    Example usages:
        guard aegis installer --flavor deb
        guard aegis installer --flavor msi --proxy http://proxy:8080
    """
    print_json(sdk.aegis.installer(flavor, proxy_configuration=proxy))


@aegis.command('provision')
@cli_handler
@praetorian_only
@click.option('--tenant', required=True, help='Tenant email (@praetorian.com)')
def provision(sdk, tenant):
    """ Provision Aegis for a tenant

    \b
    Example usages:
        guard aegis provision --tenant user@praetorian.com
    """
    print_json(sdk.aegis.provision(tenant))


@aegis.command('capabilities')
@cli_handler
@praetorian_only
@click.option('--name', default=None, help='Filter by capability name')
@click.option('--target', default=None, help='Filter by target type')
@click.option('--executor', default=None, help='Filter by executor')
@click.option('--runs-on', default=None,
              type=click.Choice(['windows', 'linux', 'macos', 'any']),
              help='Filter by platform')
def mgmt_capabilities(sdk, name, target, executor, runs_on):
    """ List Aegis management capabilities

    \b
    Example usages:
        guard aegis capabilities
        guard aegis capabilities --runs-on windows
        guard aegis capabilities --target agent
    """
    print_json(sdk.aegis.management_capabilities(
        name=name, target=target, executor=executor, runs_on=runs_on))


@aegis.command('tasks')
@cli_handler
@praetorian_only
@click.option('--key', default=None, help='Specific task key to retrieve')
def mgmt_tasks(sdk, key):
    """ List or get Aegis management tasks

    \b
    Example usages:
        guard aegis tasks
        guard aegis tasks --key task-key-123
    """
    print_json(sdk.aegis.management_tasks(key=key))


@aegis.command('create-task')
@cli_handler
@praetorian_only
@click.option('--capability', required=True, help='Management capability name')
@click.option('--client-id', required=True, help='Agent client ID (e.g. C.xxxx)')
@click.option('--agent-id', default=None, help='Specific agent ID')
@click.option('--parameters', default=None, help='JSON parameters string')
@click.option('--async', 'async_', is_flag=True, default=False, help='Run asynchronously')
@click.option('--health-check', is_flag=True, default=False,
              help='Trigger health check after task')
def create_task(sdk, capability, client_id, agent_id, parameters, async_, health_check):
    """ Create an Aegis management task

    \b
    Example usages:
        guard aegis create-task --capability install-sysmon --client-id C.abc123
        guard aegis create-task --capability run-script --client-id C.abc123 --parameters '{"script":"test.ps1"}'
    """
    params = json.loads(parameters) if parameters else None
    print_json(sdk.aegis.create_management_task(
        capability, client_id, agent_id=agent_id, parameters=params,
        async_=async_, health_check=health_check))


@aegis.command('cancel-task')
@cli_handler
@praetorian_only
@click.option('--key', required=True, help='Task key to cancel')
def cancel_task(sdk, key):
    """ Cancel an Aegis management task

    \b
    Example usages:
        guard aegis cancel-task --key task-key-123
    """
    print_json(sdk.aegis.cancel_management_task(key))


@aegis.command('tunnel-create')
@cli_handler
@praetorian_only
@click.option('--client-id', required=True, help='Agent client ID (e.g. C.xxxx)')
def tunnel_create(sdk, client_id):
    """ Create a Cloudflare tunnel for an Aegis agent

    \b
    Example usages:
        guard aegis tunnel-create --client-id C.abc123
    """
    print_json(sdk.aegis.create_tunnel(client_id))


@aegis.command('tunnel-remove')
@cli_handler
@praetorian_only
@click.option('--client-id', required=True, help='Agent client ID (e.g. C.xxxx)')
@click.option('--force', is_flag=True, default=False, help='Skip confirmation prompt')
def tunnel_remove(sdk, client_id, force):
    """ Remove a Cloudflare tunnel from an Aegis agent

    \b
    Prompts for confirmation unless --force is passed.

    \b
    Example usages:
        guard aegis tunnel-remove --client-id C.abc123
        guard aegis tunnel-remove --client-id C.abc123 --force
    """
    if not force:
        click.confirm(f'Remove Cloudflare tunnel for {client_id}?', abort=True)
    print_json(sdk.aegis.remove_tunnel(client_id))


@aegis.command('reachability-agent')
@cli_handler
@click.option('--client-id', required=True, help='Agent client ID')
@click.option('--limit', type=int, default=None, help='Max results')
def reach_agent(sdk, client_id, limit):
    """ Show assets reachable from an Aegis agent

    \b
    Example usages:
        guard aegis reachability-agent --client-id C.abc123
        guard aegis reachability-agent --client-id C.abc123 --limit 100
    """
    print_json(sdk.aegis.reachability_agent(client_id, limit=limit))


@aegis.command('reachability-asset')
@cli_handler
@click.option('--key', required=True, help='Asset key')
def reach_asset(sdk, key):
    """ Show agents that can reach a specific asset

    \b
    Example usages:
        guard aegis reachability-asset --key "#asset#10.0.1.5#10.0.1.5"
    """
    print_json(sdk.aegis.reachability_asset(key))
