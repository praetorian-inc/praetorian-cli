import click
import sys
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



@aegis.command()
@cli_handler
@click.option('--details', is_flag=True, help='Show detailed capability descriptions')
@click.option('--filter', help='Filter agents by hostname or other properties')
def list_agents(sdk, details, filter):
    """List Aegis agents with optional details"""
    result = sdk.aegis.format_agents_list(details=details, filter_text=filter)
    
    if result.get('success'):
        click.echo(result['output'])
    else:
        click.echo(f"Error: {result.get('message', 'Unknown error')}", err=True)
        sys.exit(1)


def _ssh_to_agent(sdk, client_id, user=None, local_forward=None, remote_forward=None, dynamic_forward=None, key=None, ssh_opts=None, exit_on_completion=True):
    """Thin wrapper around SDK SSH method for backward compatibility"""
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


@aegis.command()
@cli_handler
@click.argument('client_id', required=True)
@click.option('--user', '-u', help='SSH username (default: auto-detected from your email)')
@click.option('-L', '--local-forward', multiple=True, help='Local port forwarding (e.g., 8080:localhost:80)')
@click.option('-R', '--remote-forward', multiple=True, help='Remote port forwarding (e.g., 9090:localhost:3000)')
@click.option('-D', '--dynamic-forward', help='Dynamic port forwarding/SOCKS proxy (e.g., 1080)')
@click.option('--key', '-i', help='SSH private key file')
@click.option('--ssh-opts', help='Additional SSH options (e.g., "-o StrictHostKeyChecking=no")')
def ssh(sdk, client_id, user, local_forward, remote_forward, dynamic_forward, key, ssh_opts):
    """SSH to an Aegis instance using Cloudflare tunnel
    
    Uses your email username automatically (e.g., john.doe@example.com → john.doe)
    
    \b
    Arguments:
        CLIENT_ID: The client ID of the Aegis instance (e.g., C.6e012b467f9faf82-OG9F0)
    
    \b
    Example usages:
        - praetorian chariot aegis ssh C.6e012baaaaaaa-AAAAA                      # SSH as your username
        - praetorian chariot aegis ssh C.6e012baaaaaaa-AAAAA --user root          # SSH as specific user
        - praetorian chariot aegis ssh C.6e012baaaaaaa-AAAAA -L 8080:localhost:80 # With port forwarding
        - praetorian chariot aegis ssh C.6e012baaaaaaa-AAAAA -R 9090:localhost:3000
        - praetorian chariot aegis ssh C.6e012baaaaaaa-AAAAA -D 1080              # SOCKS proxy
        - praetorian chariot aegis ssh C.6e012baaaaaaa-AAAAA -L 8080:web:80 -L 9000:db:5432
        - praetorian chariot aegis ssh C.6e012baaaaaaa-AAAAA -i ~/.ssh/my_key     # Custom SSH key
        - praetorian chariot aegis ssh C.6e012baaaaaaa-AAAAA --ssh-opts "-v"     # SSH options
    """
    _ssh_to_agent(sdk, client_id, user, local_forward, remote_forward, dynamic_forward, key, ssh_opts)


@aegis.command()
@cli_handler
@click.argument('client_id', required=True)
@click.option('-c', '--capability', 'capabilities', multiple=True, help='Capability to run (e.g., windows-smb-snaffler)')
@click.option('--config', help='JSON configuration string for the job')
def job(sdk, client_id, capabilities, config):
    """Run a job on an Aegis agent
    
    Schedule security scanning jobs for the specified Aegis agent. Jobs run
    capabilities against the target asset or domain.
    
    \\b
    Arguments:
        CLIENT_ID: The client ID of the Aegis agent (e.g., C.6e012b467f9faf82-OG9F0)
    
    \\b
    Example usages:
        - praetorian chariot aegis job C.6e012b467f9faf82-OG9F0 -c windows-smb-snaffler
        - praetorian chariot aegis job C.6e012b467f9faf82-OG9F0 -c windows-domain-collection
        - praetorian chariot aegis job C.6e012b467f9faf82-OG9F0 -c linux-filesystem-scan
        - praetorian chariot aegis job C.6e012b467f9faf82-OG9F0 --config '{"Username":"admin","Password":"secret"}'
    """
    result = sdk.aegis.run_job(client_id, list(capabilities) if capabilities else None, config)
    
    if 'capabilities' in result:
        # Show available capabilities
        click.echo("Available capabilities:")
        for cap in result['capabilities']:
            name = cap.get('name', 'unknown')
            desc = cap.get('description', '')[:50]
            click.echo(f"  {name:<25} {desc}")
    elif result.get('success'):
        # Job was queued successfully
        click.echo(f"✓ Job queued successfully")
        click.echo(f"  Job ID: {result.get('job_id', 'unknown')}")
        click.echo(f"  Status: {result.get('status', 'unknown')}")
    else:
        # Error occurred
        click.echo(f"Error: {result.get('message', 'Unknown error')}", err=True)
        sys.exit(1)