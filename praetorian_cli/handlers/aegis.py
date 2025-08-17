import click
from praetorian_cli.handlers.chariot import chariot
from praetorian_cli.handlers.cli_decorators import cli_handler
from praetorian_cli.interface_adapters.aegis_commands import aegis_shared, AegisContext


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
    # Create CLI context and invoke shared command
    aegis_ctx = AegisContext(sdk)
    ctx.obj = aegis_ctx
    
    # Get the shared command and invoke it
    shared_cmd = aegis_shared.get_command(ctx, 'list')
    ctx.invoke(shared_cmd, details=details, filter=filter)


@aegis.command('ssh')
@cli_handler
@click.option('-D', '--dynamic-forward', help='Dynamic port forwarding/SOCKS proxy (e.g., 1080)')
@click.option('-L', '--local-forward', multiple=True, help='Local port forwarding (e.g., 8080:localhost:80)')
@click.option('-R', '--remote-forward', multiple=True, help='Remote port forwarding (e.g., 9090:localhost:3000)')
@click.option('-u', '--user', help='SSH username (default: auto-detected from email)')
@click.option('-i', '--key', help='SSH private key file')
@click.option('--ssh-opts', help='Additional SSH options (e.g., "-o StrictHostKeyChecking=no")')
@click.argument('client_id', required=True)
@click.pass_context
def ssh(ctx, sdk, dynamic_forward, local_forward, remote_forward, user, key, ssh_opts, client_id):
    """Connect to an Aegis agent via SSH"""
    # Create CLI context and invoke shared command
    aegis_ctx = AegisContext(sdk)
    ctx.obj = aegis_ctx
    
    # Get the shared command and invoke it
    shared_cmd = aegis_shared.get_command(ctx, 'ssh')
    ctx.invoke(shared_cmd, dynamic_forward=dynamic_forward, local_forward=local_forward,
               remote_forward=remote_forward, user=user, key=key, ssh_opts=ssh_opts, client_id=client_id)


@aegis.command('job')
@cli_handler
@click.option('-c', '--capability', 'capabilities', multiple=True, help='Capability to run (e.g., windows-smb-snaffler)')
@click.option('--config', help='JSON configuration string for the job')
@click.argument('client_id', required=True)
@click.pass_context
def job(ctx, sdk, capabilities, config, client_id):
    """Run a job on an Aegis agent"""
    # Create CLI context and invoke shared command
    aegis_ctx = AegisContext(sdk)
    ctx.obj = aegis_ctx
    
    # Get the shared command and invoke it
    shared_cmd = aegis_shared.get_command(ctx, 'job')
    ctx.invoke(shared_cmd, capabilities=capabilities, config=config, client_id=client_id)


@aegis.command('info')
@cli_handler
@click.argument('client_id', required=True)
@click.pass_context
def info(ctx, sdk, client_id):
    """Show detailed information for an agent"""
    # Create CLI context and invoke shared command
    aegis_ctx = AegisContext(sdk)
    ctx.obj = aegis_ctx
    
    # Get the shared command and invoke it
    shared_cmd = aegis_shared.get_command(ctx, 'info')
    ctx.invoke(shared_cmd, client_id=client_id)


# Keep the backward compatibility function for now
def _ssh_to_agent(sdk, client_id, user=None, local_forward=None, remote_forward=None, dynamic_forward=None, key=None, ssh_opts=None, exit_on_completion=True):
    """Thin wrapper around SDK SSH method for backward compatibility"""
    import sys
    try:
        exit_code = sdk.aegis.ssh_to_agent(
            client_id=client_id,
            user=user,
            local_forward=local_forward or [],
            remote_forward=remote_forward or [],
            dynamic_forward=dynamic_forward,
            key=key,
            ssh_opts=ssh_opts,
            display_info=True
        )
        
        if exit_on_completion:
            sys.exit(exit_code)
        else:
            return exit_code
            
    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        if exit_on_completion:
            sys.exit(1)
        else:
            return 1