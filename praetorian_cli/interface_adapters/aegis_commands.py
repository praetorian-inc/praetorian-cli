"""
Interface adapters for Aegis commands across CLI and TUI.

This module provides interface adapter components that enable Aegis commands
to work consistently across both CLI and TUI contexts. The adapters handle
context-aware execution, output formatting, and state management while
delegating business logic to the SDK layer.
"""

import click
import sys


class AegisContext:
    """Context object for Aegis commands that works in both CLI and TUI"""
    
    def __init__(self, sdk, console=None, tui_state=None):
        self.sdk = sdk
        self.console = console  # Rich console for TUI, None for CLI
        self.tui_state = tui_state  # TUI state (selected_agent, etc.)
        self.is_tui = console is not None
    
    def echo(self, message, err=False, color=None):
        """Output message appropriate for context (CLI or TUI)"""
        if self.is_tui and self.console:
            # TUI output with Rich formatting
            style = None
            if color == 'red' or err:
                style = 'red'
            elif color == 'green':
                style = 'green'
            elif color == 'yellow':
                style = 'yellow'
            
            self.console.print(message, style=style)
        else:
            # CLI output with Click
            click.echo(message, err=err, color=color)
    
    def get_selected_agent(self):
        """Get the currently selected agent"""
        if self.tui_state and hasattr(self.tui_state, 'selected_agent'):
            return self.tui_state.selected_agent
        return None
    
    def set_selected_agent(self, agent):
        """Set the currently selected agent (TUI only)"""
        if self.tui_state and hasattr(self.tui_state, 'selected_agent'):
            self.tui_state.selected_agent = agent


# Create a Click group for Aegis commands
@click.group(invoke_without_command=True)
@click.pass_context  
def aegis_shared(ctx):
    """Aegis agent management commands"""
    if ctx.invoked_subcommand is None:
        # When no subcommand, show help
        click.echo(ctx.get_help())


@aegis_shared.command('list')
@click.option('--details', is_flag=True, help='Show detailed agent information')
@click.option('--filter', help='Filter agents by hostname or other properties')
@click.pass_context
def list_agents(ctx, details, filter):
    """List Aegis agents with optional details
    
    Shows all available Aegis agents with their status and basic information.
    Use --details for comprehensive system information including network interfaces,
    tunnel status, and health check data.
    
    Examples:
        list                    # Show basic agent list
        list --details          # Show detailed information  
        list --filter windows   # Filter by OS or hostname
        list --filter C.abc123  # Filter by client ID
    """
    aegis_ctx = ctx.obj
    
    try:
        result = aegis_ctx.sdk.aegis.format_agents_list(details=details, filter_text=filter)
        
        if result.get('success'):
            aegis_ctx.echo(result['output'])
        else:
            aegis_ctx.echo(f"Error: {result.get('message', 'Unknown error')}", err=True, color='red')
            if not aegis_ctx.is_tui:
                sys.exit(1)
                
    except Exception as e:
        aegis_ctx.echo(f"Error: {e}", err=True, color='red')
        if not aegis_ctx.is_tui:
            sys.exit(1)


@aegis_shared.command('set')
@click.argument('identifier')
@click.pass_context
def set_agent(ctx, identifier):
    """Set current agent by number, client ID, or hostname
    
    Selects an agent as the target for subsequent operations like SSH and jobs.
    The identifier can be an agent number (1-N), client ID, or hostname.
    
    Examples:
        set 1                   # Select first agent by number
        set C.6e012b467f9faf82  # Select by client ID
        set kali-vm             # Select by hostname
    """
    aegis_ctx = ctx.obj
    
    # This command only makes sense in TUI context
    if not aegis_ctx.is_tui:
        aegis_ctx.echo("The 'set' command is only available in the TUI interface.", err=True, color='red')
        return
    
    try:
        agents_data, _ = aegis_ctx.sdk.aegis.list()
        selected_agent = None
        
        # Try by agent number first
        if identifier.isdigit():
            agent_num = int(identifier)
            if 1 <= agent_num <= len(agents_data):
                selected_agent = agents_data[agent_num - 1]
        
        # Try by client ID or hostname
        if not selected_agent:
            for agent in agents_data:
                if (agent.client_id == identifier or 
                    (agent.hostname and agent.hostname.lower() == identifier.lower())):
                    selected_agent = agent
                    break
        
        if selected_agent:
            aegis_ctx.set_selected_agent(selected_agent)
            hostname = selected_agent.hostname or 'Unknown'
            client_id = selected_agent.client_id or 'N/A'
            aegis_ctx.echo(f"Selected agent: {hostname} ({client_id})", color='green')
        else:
            aegis_ctx.echo(f"Agent not found: {identifier}", err=True, color='red')
            
    except Exception as e:
        aegis_ctx.echo(f"Error: {e}", err=True, color='red')


@aegis_shared.command('ssh')
@click.option('-D', '--dynamic-forward', help='Dynamic port forwarding/SOCKS proxy (e.g., 1080)')
@click.option('-L', '--local-forward', multiple=True, help='Local port forwarding (e.g., 8080:localhost:80)')
@click.option('-R', '--remote-forward', multiple=True, help='Remote port forwarding (e.g., 9090:localhost:3000)')
@click.option('-u', '--user', help='SSH username (default: auto-detected from email)')
@click.option('-i', '--key', help='SSH private key file')
@click.option('--ssh-opts', help='Additional SSH options (e.g., "-o StrictHostKeyChecking=no")')
@click.argument('client_id', required=False)
@click.pass_context
def ssh_command(ctx, dynamic_forward, local_forward, remote_forward, user, key, ssh_opts, client_id):
    """Connect to an Aegis agent via SSH
    
    Establishes SSH connection to the specified agent using Cloudflare tunnel.
    If no client_id is provided in CLI mode, shows error. In TUI mode, uses
    the currently selected agent.
    
    Examples:
        ssh C.6e012b467f9faf82                    # Basic SSH connection
        ssh C.6e012b467f9faf82 -u root            # SSH as specific user  
        ssh C.6e012b467f9faf82 -D 1080            # With SOCKS proxy
        ssh C.6e012b467f9faf82 -L 8080:web:80     # With port forwarding
        ssh C.6e012b467f9faf82 -i ~/.ssh/mykey    # With custom SSH key
    """
    aegis_ctx = ctx.obj
    
    # Determine target client_id
    target_client_id = client_id
    if not target_client_id and aegis_ctx.is_tui:
        # In TUI, use selected agent
        selected_agent = aegis_ctx.get_selected_agent()
        if selected_agent:
            target_client_id = selected_agent.client_id
        else:
            aegis_ctx.echo("No agent selected. Use 'set <id>' to select an agent first.", err=True, color='red')
            return
    elif not target_client_id:
        # In CLI, client_id is required
        aegis_ctx.echo("Error: Missing client_id argument", err=True, color='red')
        aegis_ctx.echo(ctx.get_help())
        if not aegis_ctx.is_tui:
            sys.exit(1)
        return
    
    try:
        exit_code = aegis_ctx.sdk.aegis.ssh_to_agent(
            client_id=target_client_id,
            user=user,
            local_forward=list(local_forward),
            remote_forward=list(remote_forward),
            dynamic_forward=dynamic_forward,
            key=key,
            ssh_opts=ssh_opts,
            display_info=True
        )
        
        # In CLI mode, exit with the SSH exit code
        if not aegis_ctx.is_tui:
            sys.exit(exit_code)
            
    except Exception as e:
        aegis_ctx.echo(f"Error: {e}", err=True, color='red')
        if not aegis_ctx.is_tui:
            sys.exit(1)


@aegis_shared.command('job')
@click.option('-c', '--capability', 'capabilities', multiple=True, help='Capability to run (e.g., windows-smb-snaffler)')
@click.option('--config', help='JSON configuration string for the job')
@click.argument('client_id', required=False)
@click.pass_context
def job_command(ctx, capabilities, config, client_id):
    """Run a job on an Aegis agent
    
    Schedule security scanning jobs for the specified Aegis agent. If no
    capabilities are provided, shows available capabilities. In TUI mode,
    uses the currently selected agent if no client_id provided.
    
    Examples:
        job C.6e012b467f9faf82                           # List available capabilities
        job C.6e012b467f9faf82 -c windows-smb-snaffler  # Run specific capability
        job C.6e012b467f9faf82 -c linux-filesystem-scan # Run Linux capability
        job C.6e012b467f9faf82 --config '{"timeout":300}' # With configuration
    """
    aegis_ctx = ctx.obj
    
    # Determine target client_id  
    target_client_id = client_id
    if not target_client_id and aegis_ctx.is_tui:
        # In TUI, use selected agent
        selected_agent = aegis_ctx.get_selected_agent()
        if selected_agent:
            target_client_id = selected_agent.client_id
        else:
            aegis_ctx.echo("No agent selected. Use 'set <id>' to select an agent first.", err=True, color='red')
            return
    elif not target_client_id:
        # In CLI, client_id is required
        aegis_ctx.echo("Error: Missing client_id argument", err=True, color='red')
        aegis_ctx.echo(ctx.get_help())
        if not aegis_ctx.is_tui:
            sys.exit(1)
        return
    
    try:
        result = aegis_ctx.sdk.aegis.run_job(
            target_client_id, 
            list(capabilities) if capabilities else None, 
            config
        )
        
        if 'capabilities' in result:
            # Show available capabilities
            aegis_ctx.echo("Available capabilities:")
            for cap in result['capabilities']:
                name = cap.get('name', 'unknown')
                desc = cap.get('description', '')[:50]
                aegis_ctx.echo(f"  {name:<25} {desc}")
        elif result.get('success'):
            # Job was queued successfully
            aegis_ctx.echo(f"✓ Job queued successfully", color='green')
            aegis_ctx.echo(f"  Job ID: {result.get('job_id', 'unknown')}")
            aegis_ctx.echo(f"  Status: {result.get('status', 'unknown')}")
        else:
            # Error occurred
            aegis_ctx.echo(f"Error: {result.get('message', 'Unknown error')}", err=True, color='red')
            if not aegis_ctx.is_tui:
                sys.exit(1)
                
    except Exception as e:
        aegis_ctx.echo(f"Error: {e}", err=True, color='red')
        if not aegis_ctx.is_tui:
            sys.exit(1)


@aegis_shared.command('info')
@click.argument('client_id', required=False)
@click.pass_context
def info_command(ctx, client_id):
    """Show detailed information for an agent
    
    Displays comprehensive system information including OS details, network
    interfaces, tunnel status, and health check data. In TUI mode, uses
    the currently selected agent if no client_id provided.
    
    Examples:
        info C.6e012b467f9faf82  # Show info for specific agent
        info                     # In TUI: show info for selected agent
    """
    aegis_ctx = ctx.obj
    
    # Determine target client_id
    target_client_id = client_id
    if not target_client_id and aegis_ctx.is_tui:
        # In TUI, use selected agent
        selected_agent = aegis_ctx.get_selected_agent()
        if selected_agent:
            target_client_id = selected_agent.client_id
        else:
            aegis_ctx.echo("No agent selected. Use 'set <id>' to select an agent first.", err=True, color='red')
            return
    elif not target_client_id:
        # In CLI, client_id is required
        aegis_ctx.echo("Error: Missing client_id argument", err=True, color='red')
        aegis_ctx.echo(ctx.get_help())
        if not aegis_ctx.is_tui:
            sys.exit(1)
        return
    
    try:
        agent = aegis_ctx.sdk.aegis.get_by_client_id(target_client_id)
        if not agent:
            aegis_ctx.echo(f"Agent not found: {target_client_id}", err=True, color='red')
            if not aegis_ctx.is_tui:
                sys.exit(1)
            return
        
        # Display detailed info using the same logic as list command
        
        # Display detailed info (reuse the formatting logic)
        hostname = agent.hostname or 'Unknown'
        client_id_display = agent.client_id or 'N/A'
        os_info = f"{agent.os or 'unknown'} {agent.os_version or ''}".strip()
        
        aegis_ctx.echo(f"\n{hostname} ({client_id_display})")
        aegis_ctx.echo(f"  OS: {os_info}")
        aegis_ctx.echo(f"  Architecture: {agent.architecture or 'Unknown'}")
        aegis_ctx.echo(f"  FQDN: {agent.fqdn or 'N/A'}")
        
        # Health check details
        if agent.has_tunnel:
            cf_status = agent.health_check.cloudflared_status
            aegis_ctx.echo(f"  Tunnel: {cf_status.tunnel_name or 'N/A'}")
            aegis_ctx.echo(f"  Public hostname: {cf_status.hostname or 'N/A'}")
            if cf_status.authorized_users:
                aegis_ctx.echo(f"  Authorized users: {cf_status.authorized_users}")
        else:
            aegis_ctx.echo("  Tunnel: Not configured")
            
        # Network interfaces
        ips = agent.ip_addresses
        if ips:
            aegis_ctx.echo(f"  IP addresses: {', '.join(ips)}")
            
    except Exception as e:
        aegis_ctx.echo(f"Error: {e}", err=True, color='red')
        if not aegis_ctx.is_tui:
            sys.exit(1)