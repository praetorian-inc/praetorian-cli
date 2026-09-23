import click
from praetorian_cli.handlers.chariot import chariot
from praetorian_cli.handlers.cli_decorators import cli_handler


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


@aegis.command('endpoints')
@cli_handler
@click.option('-f', '--filter', 'filter_text', default='',
              help='Filter by endpoint ID, kind, hostname, OS or architecture')
@click.option('--online', 'online_only', is_flag=True,
              help='Show only endpoints currently connected to Guard')
@click.pass_context
def endpoints(ctx, sdk, filter_text, online_only):
    """List enrolled Aegis endpoints

    Endpoints are a different inventory from the agents in "guard aegis list". An
    endpoint receives tasks dispatched by Guard rather than being reached over SSH,
    and a mobile device running the Aegis agent appears only here.

    \b
    Example usages:
        - guard aegis endpoints
        - guard aegis endpoints --online
        - guard aegis endpoints --filter arm64
    """
    enrolled, _ = sdk.endpoints.list(filter_text=filter_text, online_only=online_only)

    if not enrolled:
        click.echo('No endpoints found.')
        return

    click.echo(f"{'ENDPOINT ID':<38} {'STATE':<14} {'KIND':<8} SYSTEM")
    for endpoint in enrolled:
        profile = endpoint.get('profile') or {}
        system = ' '.join(d for d in (profile.get('hostname'), profile.get('os'), profile.get('arch')) if d)
        click.echo(f"{endpoint.get('endpointId', 'unknown'):<38} "
                   f"{endpoint.get('connectionState', 'unknown'):<14} "
                   f"{endpoint.get('kind', ''):<8} {system}")


@aegis.command('job')
@cli_handler
@click.option('-c', '--capability', 'capabilities', multiple=True,
              help='Capability to run (e.g., windows-smb-snaffler, android-device-survey)')
@click.option('--config', help='JSON configuration string for the job')
@click.option('-p', '--package',
              help='Android application ID to target, e.g. com.bank.app. Upload the APK first with "guard add apk".')
@click.option('-e', '--endpoint', 'endpoint_id',
              help='Enrolled endpoint to run the job on, as listed by "guard aegis endpoints"')
@click.argument('client_id', required=False)
@click.pass_context
def job(ctx, sdk, capabilities, config, package, endpoint_id, client_id):
    """Run a job on an Aegis agent or an enrolled endpoint

    Name the target with either CLIENT_ID, for an agent's own host, or --package, for
    an Android application already registered with "guard add apk". Without -c, the
    capabilities available for that target are listed instead of a job being run.

    \b
    Example usages:
        - guard aegis job C.6e012b467f9faf82-OG9F0 -c linux-enum
        - guard aegis job --package com.bank.app
        - guard aegis job --package com.bank.app -c android-device-survey -e 16169bc5-7943-4783-af81-c4735616f7e9
        - guard aegis job --package com.bank.app -c android-device-command -e 16169bc5-7943-4783-af81-c4735616f7e9 --config '{"command": "getprop ro.build.fingerprint"}'
    """
    if client_id and package:
        click.echo('A job has one target: pass either CLIENT_ID or --package, not both.', err=True)
        return

    if not client_id and not package:
        click.echo('No target. Pass an agent CLIENT_ID, or --package to target an APK.', err=True)
        return

    hostname = None
    if client_id:
        agent = sdk.aegis.get_by_client_id(client_id)
        if not agent:
            click.echo(f"Agent not found: {client_id}", err=True)
            return
        hostname = agent.hostname

    try:
        result = sdk.aegis.run_job(
            capabilities=list(capabilities) if capabilities else None,
            hostname=hostname,
            package=package,
            endpoint_id=endpoint_id,
            config=config,
        )

        if 'capabilities' in result:
            if not result['capabilities']:
                click.echo('No capabilities available for this target.')
                return
            click.echo("Available capabilities:")
            for cap in result['capabilities']:
                name = cap.get('name', 'unknown')
                desc = cap.get('description', '')[:50]
                click.echo(f"  {name:<25} {desc}")
        elif result.get('success'):
            click.echo("✓ Job queued successfully")
            click.echo(f"  Job ID: {result.get('job_id', 'unknown')}")
            click.echo(f"  Target: {result.get('target_key', 'unknown')}")
            if result.get('endpoint_id'):
                click.echo(f"  Endpoint: {result['endpoint_id']}")
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
