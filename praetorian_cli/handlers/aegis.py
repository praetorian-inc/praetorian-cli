import click
import subprocess
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
        - praetorian chariot aegis ssh C.6e012baaaaaaa-AAAAA                    # SSH as your username
        - praetorian chariot aegis ssh C.6e012baaaaaaa-AAAAA--user root         # SSH as specific user
        - praetorian chariot aegis ssh C.6e012baaaaaaa-AAAAA-L 8080:localhost:80 # With port forwarding
        - praetorian chariot aegis ssh C.6e012baaaaaaa-AAAAA-R 9090:localhost:3000
        - praetorian chariot aegis ssh C.6e012baaaaaaa-AAAAA-D 1080             # SOCKS proxy
        - praetorian chariot aegis ssh C.6e012baaaaaaa-AAAAA-L 8080:web:80 -L 9000:db:5432
        - praetorian chariot aegis ssh C.6e012baaaaaaa-AAAAA-i ~/.ssh/my_key    # Custom SSH key
        - praetorian chariot aegis ssh C.6e012baaaaaaa-AAAAA--ssh-opts "-v"    # SSH options
    """
    try:
        # Determine SSH username using the centralized method
        if not user:
            _, user = sdk.get_current_user()
        
        # Get agent details
        agent = sdk.aegis.get_by_client_id(client_id)
        if not agent:
            click.echo(f"Error: No Aegis instance found with client ID: {client_id}", err=True)
            sys.exit(1)
        
        hostname = agent.get('hostname', 'Unknown')
        health = agent.get('health_check', {})
        
        # Check if Cloudflare tunnel is available
        if not (health and health.get('cloudflared_status')):
            click.echo(f"Error: No Cloudflare tunnel available for {hostname} ({client_id})", err=True)
            click.echo("SSH access requires an active Cloudflare tunnel.", err=True)
            sys.exit(1)
        
        # Get tunnel information
        cf_status = health['cloudflared_status']
        public_hostname = cf_status.get('hostname')
        authorized_users = cf_status.get('authorized_users', '')
        tunnel_name = cf_status.get('tunnel_name', 'N/A')
        
        if not public_hostname:
            click.echo(f"Error: No public hostname found in tunnel configuration for {hostname}", err=True)
            sys.exit(1)
        
        # Check if user is authorized (if authorization is configured)
        if authorized_users:
            users_list = [u.strip() for u in authorized_users.split(',')]
            if user not in users_list:
                click.echo(f"Warning: User '{user}' may not be authorized for this tunnel.", err=True)
                click.echo(f"Authorized users: {', '.join(users_list)}", err=True)
                click.echo("Proceeding anyway...", err=True)
        
        # Build SSH command
        ssh_command = ['ssh']
        
        # Add SSH key if specified
        if key:
            ssh_command.extend(['-i', key])
        
        # Add local port forwarding (-L)
        for forward in local_forward:
            ssh_command.extend(['-L', forward])
        
        # Add remote port forwarding (-R)
        for forward in remote_forward:
            ssh_command.extend(['-R', forward])
        
        # Add dynamic port forwarding (-D)
        if dynamic_forward:
            ssh_command.extend(['-D', dynamic_forward])
        
        # Add additional SSH options
        if ssh_opts:
            import shlex
            ssh_command.extend(shlex.split(ssh_opts))
        
        # Add the target
        ssh_command.append(f'{user}@{public_hostname}')
        
        # Execute SSH command
        click.echo(f"Connecting to {hostname} via {public_hostname}...")
        click.echo(f"Tunnel: {tunnel_name}")
        click.echo(f"SSH user: {user}")
        
        # Show active port forwarding
        if local_forward:
            click.echo(f"Local forwarding: {', '.join(local_forward)}")
        if remote_forward:
            click.echo(f"Remote forwarding: {', '.join(remote_forward)}")
        if dynamic_forward:
            click.echo(f"SOCKS proxy: localhost:{dynamic_forward}")
        
        click.echo("")
        
        try:
            # Use subprocess.run with direct terminal interaction
            result = subprocess.run(ssh_command)
            sys.exit(result.returncode)
        except KeyboardInterrupt:
            click.echo("\nSSH connection interrupted.")
            sys.exit(130)
        except FileNotFoundError:
            click.echo("Error: SSH command not found. Please ensure SSH is installed and in your PATH.", err=True)
            sys.exit(1)
            
    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)