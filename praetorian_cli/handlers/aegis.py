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
