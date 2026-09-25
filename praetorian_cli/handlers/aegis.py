import click
from praetorian_cli.handlers.chariot import chariot
from praetorian_cli.handlers.cli_decorators import cli_handler
from praetorian_cli.ui.aegis.commands.enrollment import (
    enrollment_error_message,
    pending_enrollment_lines,
)
from praetorian_cli.ui.aegis.commands.network_policy import (
    DEFAULT_RULE_IDS,
    apply_policy_operation,
    network_policy_error_message,
    network_policy_lines,
)


def _enrollment_debug_enabled():
    ctx = click.get_current_context()
    return bool(ctx.find_root().params.get('debug', False))


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


@aegis.group('enrollment')
def enrollment():
    """Inspect and approve Aegis v2 endpoint enrollment user codes."""
    pass


@enrollment.command('inspect')
@cli_handler
@click.argument('user_code', required=True)
def inspect_enrollment(sdk, user_code):
    """Inspect a pending Aegis v2 endpoint enrollment user code."""
    try:
        pending = sdk.aegis.inspect_enrollment(user_code)
    except Exception as exc:
        if _enrollment_debug_enabled():
            raise
        raise click.ClickException(enrollment_error_message(exc)) from exc

    click.echo('Pending Aegis v2 enrollment:')
    for line in pending_enrollment_lines(pending):
        click.echo(f'  {line}')


@enrollment.command('approve')
@cli_handler
@click.argument('user_code', required=True)
@click.option('-y', '--yes', is_flag=True, default=False, help='Approve without interactive confirmation')
def approve_enrollment(sdk, user_code, yes):
    """Inspect, confirm, and approve an Aegis v2 endpoint enrollment user code."""
    try:
        pending = sdk.aegis.inspect_enrollment(user_code)
    except Exception as exc:
        if _enrollment_debug_enabled():
            raise
        raise click.ClickException(enrollment_error_message(exc)) from exc

    click.echo('Pending Aegis v2 enrollment:')
    for line in pending_enrollment_lines(pending):
        click.echo(f'  {line}')

    if not yes and not click.confirm('Approve this enrollment?', default=False):
        click.echo('Cancelled')
        return

    try:
        result = sdk.aegis.approve_enrollment(user_code)
    except Exception as exc:
        if _enrollment_debug_enabled():
            raise
        raise click.ClickException(enrollment_error_message(exc)) from exc
    status = result.get('status', 'approved') if isinstance(result, dict) else 'approved'
    click.echo(f'Enrollment {status}')


@aegis.group('network-policy')
def network_policy():
    """View and customize Aegis v2 host-enforced egress policy."""
    pass


@network_policy.command('show')
@cli_handler
@click.argument('endpoint_id', required=True)
def show_network_policy(sdk, endpoint_id):
    """Show policy status, protected connectivity, and every deny rule."""
    policy = _get_network_policy(sdk, endpoint_id)
    _echo_network_policy(policy)


@network_policy.group('default')
def network_policy_default():
    """Remove or restore Guard's built-in deny rules."""
    pass


@network_policy_default.command('remove')
@cli_handler
@click.argument('endpoint_id', required=True)
@click.argument('rule_id', type=click.Choice(DEFAULT_RULE_IDS))
@click.option('-y', '--yes', is_flag=True, help='Save without interactive confirmation')
def remove_default_network_policy_rule(sdk, endpoint_id, rule_id, yes):
    """Remove a built-in deny rule from an endpoint policy."""
    _change_network_policy(sdk, endpoint_id, {
        'kind': 'default',
        'action': 'remove',
        'rule_id': rule_id,
        'yes': yes,
    })


@network_policy_default.command('restore')
@cli_handler
@click.argument('endpoint_id', required=True)
@click.argument('rule_id', type=click.Choice(DEFAULT_RULE_IDS))
@click.option('-y', '--yes', is_flag=True, help='Save without interactive confirmation')
def restore_default_network_policy_rule(sdk, endpoint_id, rule_id, yes):
    """Restore a built-in deny rule to an endpoint policy."""
    _change_network_policy(sdk, endpoint_id, {
        'kind': 'default',
        'action': 'restore',
        'rule_id': rule_id,
        'yes': yes,
    })


@network_policy.group('deny')
def network_policy_deny():
    """Add or remove custom IP/CIDR deny rules."""
    pass


@network_policy_deny.command('add')
@cli_handler
@click.argument('endpoint_id', required=True)
@click.argument('destination', required=True)
@click.option(
    '--tcp-ports',
    help='Comma-separated TCP ports; omit to deny all traffic',
)
@click.option('-y', '--yes', is_flag=True, help='Save without interactive confirmation')
def add_network_policy_deny(sdk, endpoint_id, destination, tcp_ports, yes):
    """Add a custom deny rule for a canonical IP address or CIDR."""
    _change_network_policy(sdk, endpoint_id, {
        'kind': 'deny-add',
        'selector': destination,
        'tcp_ports': tcp_ports,
        'ports_supplied': tcp_ports is not None,
        'yes': yes,
    })


@network_policy_deny.command('remove')
@cli_handler
@click.argument('endpoint_id', required=True)
@click.argument('rule', required=True)
@click.option(
    '--tcp-ports',
    help='Comma-separated TCP ports when selecting an exact rule',
)
@click.option('-y', '--yes', is_flag=True, help='Save without interactive confirmation')
def remove_network_policy_deny(sdk, endpoint_id, rule, tcp_ports, yes):
    """Remove a custom deny rule by displayed number or exact destination."""
    _change_network_policy(sdk, endpoint_id, {
        'kind': 'deny-remove',
        'selector': rule,
        'tcp_ports': tcp_ports,
        'ports_supplied': tcp_ports is not None,
        'yes': yes,
    })


def _change_network_policy(sdk, endpoint_id, operation):
    policy = _get_network_policy(sdk, endpoint_id)
    try:
        updated_fields, change = apply_policy_operation(policy, operation)
    except ValueError as exc:
        raise click.ClickException(str(exc)) from exc
    if updated_fields is None:
        click.echo(change)
        return
    if not operation['yes'] and not click.confirm(
        f'{change} Save this endpoint network policy?',
        default=False,
    ):
        click.echo('Cancelled')
        return
    try:
        updated = sdk.aegis.update_endpoint_network_policy(
            endpoint_id,
            policy['revision'],
            updated_fields['disabledDefaultRuleIds'],
            updated_fields['customDenyRules'],
        )
    except Exception as exc:
        _raise_network_policy_error(exc)
    click.echo('Endpoint network policy saved')
    _echo_network_policy(updated)


def _get_network_policy(sdk, endpoint_id):
    try:
        return sdk.aegis.get_endpoint_network_policy(endpoint_id)
    except Exception as exc:
        _raise_network_policy_error(exc)


def _echo_network_policy(policy):
    try:
        lines = network_policy_lines(policy)
    except ValueError as exc:
        raise click.ClickException(str(exc)) from exc
    for line in lines:
        click.echo(line)


def _raise_network_policy_error(exc):
    if _enrollment_debug_enabled():
        raise exc
    raise click.ClickException(network_policy_error_message(exc)) from exc


@aegis.command('job')
@cli_handler
@click.option('-c', '--capability', 'capabilities', multiple=True,
              help='Capability to run (e.g., windows-smb-snaffler, android-device-survey)')
@click.option('--config', help='JSON configuration string for the job')
@click.option('-p', '--package',
              help='Android application ID to target, e.g. com.bank.app. Upload the APK first with "guard add apk".')
@click.option('-e', '--endpoint', 'endpoint_id',
              help='Enrolled Aegis v2 endpoint to run the job on, as shown by "guard aegis list --details"')
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
