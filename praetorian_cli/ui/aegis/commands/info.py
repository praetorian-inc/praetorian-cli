from praetorian_cli.sdk.model.aegis import online_window_seconds_for_agent
from ..constants import DEFAULT_COLORS
from ..utils import agent_account_info, agent_display_id, is_v2_agent


def handle_info(menu, args):
    """Show detailed information for the selected agent."""
    if not menu.selected_agent:
        menu.console.print("\n  No agent selected. Use 'set <id>' to select one.\n")
        menu.pause()
        return

    # Check for raw flag
    raw = ('--raw' in args) or ('-r' in args)

    selected_agent = menu.selected_agent
    if hasattr(menu, 'refresh_selected_agent'):
        selected_agent = menu.refresh_selected_agent()

    try:
        _show_agent_info(menu, selected_agent, raw=raw)
    except Exception as e:
        colors = getattr(menu, 'colors', DEFAULT_COLORS)
        menu.console.print(f"[{colors['error']}]Error getting agent info: {e}[/{colors['error']}]")
        menu.pause()


def _show_agent_info(menu, agent, raw=False):
    """Show detailed agent info with clean formatting"""
    import json
    from datetime import datetime
    
    colors = getattr(menu, 'colors', DEFAULT_COLORS)
    hostname = agent.hostname or 'Unknown'

    # Clear screen and show header
    menu.clear_screen()
    menu.console.print()
    menu.console.print(f"  [{colors['primary']}]Agent Details[/{colors['primary']}]")
    menu.console.print()

    if raw:
        # Raw JSON dump with minimal styling
        menu.console.print(f"  [{colors['dim']}]Raw agent data:[/{colors['dim']}]")
        menu.console.print()
        # Convert agent to dict for JSON serialization
        agent_dict = agent.to_dict() if hasattr(agent, 'to_dict') else agent.__dict__
        json_lines = json.dumps(agent_dict, default=str, indent=2).split('\n')
        for line in json_lines:
            menu.console.print(f"  {line}")
        menu.pause()
        return
    
    # Gather agent info
    os_info = (agent.os or 'unknown').lower()
    os_version = agent.os_version or ''
    architecture = agent.architecture or 'Unknown'
    fqdn = agent.fqdn or 'N/A'
    display_id = agent_display_id(agent) or 'N/A'
    version = getattr(agent, 'version', 'v1')
    last_seen = agent.last_seen_at or 0
    health = agent.health_check
    cf_status = health.cloudflared_status if health else None
    
    # Get network interfaces and extract IP addresses
    network_interfaces = agent.network_interfaces or []
    ip_info = []
    
    # Extract IPs from network interfaces
    if network_interfaces:
        for interface in network_interfaces:
            if hasattr(interface, 'name'):  # NetworkInterface object
                # Get interface name
                iface_name = interface.name or ''
                
                # Get IP addresses from the ip_addresses field (it's a list)
                ip_addresses = interface.ip_addresses or []
                
                # Add each IP with interface name
                for ip in ip_addresses:
                    if ip:  # Skip empty strings
                        if iface_name and iface_name != 'lo':  # Skip loopback
                            ip_info.append(f"{ip} ({iface_name})")
                        elif iface_name != 'lo':
                            ip_info.append(ip)
    
    # Compute status
    current_time = datetime.now().timestamp()
    if last_seen > 0:
        last_seen_seconds = last_seen / 1000000 if last_seen > 1000000000000 else last_seen
        online_window_seconds = online_window_seconds_for_agent(agent)
        is_online = abs(current_time - last_seen_seconds) < online_window_seconds
        last_seen_str = datetime.fromtimestamp(last_seen_seconds).strftime("%Y-%m-%d %H:%M:%S")
        if is_online:
            status_text = f"[{colors['success']}]● online[/{colors['success']}]"
        else:
            status_text = f"[{colors['error']}]○ offline[/{colors['error']}]"
    else:
        last_seen_str = "never"
        status_text = f"[{colors['error']}]○ offline[/{colors['error']}]"
        is_online = False

    # Simple, clean output
    menu.console.print(f"  [bold white]{hostname}[/bold white]  {status_text}")
    menu.console.print(f"  [{colors['dim']}]{fqdn}[/{colors['dim']}]")
    menu.console.print()
    
    # System info
    menu.console.print(f"  [{colors['dim']}]System[/{colors['dim']}]")
    menu.console.print(f"    OS:           {os_info} {os_version}")
    menu.console.print(f"    Architecture: {architecture}")
    if ip_info:
        if len(ip_info) == 1:
            menu.console.print(f"    IP:           {ip_info[0]}")
        else:
            menu.console.print(f"    IPs:          {ip_info[0]}")
            for ip in ip_info[1:]:
                menu.console.print(f"                  {ip}")
    if is_v2_agent(agent):
        menu.console.print(f"    Version:      {version}")
        menu.console.print(f"    Endpoint ID:  {display_id}")
        acct_info = agent_account_info(agent, getattr(menu, 'agent_account_map', {}))
        if acct_info:
            account_name = acct_info.get('display_name') or acct_info.get('account_email')
            if account_name:
                menu.console.print(f"    Account:      {account_name}")
    else:
        client_id = agent.client_id or 'N/A'
        menu.console.print(f"    Client ID:    {client_id[:40]}...")
    menu.console.print(f"    Last seen:    {last_seen_str}")
    menu.console.print()
    
    # Tunnel info
    if cf_status:
        tunnel_name = cf_status.tunnel_name or 'N/A'
        public_hostname = cf_status.hostname or 'N/A'
        authorized_users = cf_status.authorized_users or ''
        
        menu.console.print(f"  [{colors['warning']}]Tunnel active[/{colors['warning']}]")
        menu.console.print(f"    Name:      {tunnel_name}")
        menu.console.print(f"    Public:    {public_hostname}")
        
        if authorized_users:
            users_list = [u.strip() for u in authorized_users.split(',')]
            menu.console.print(f"    Authorized: {', '.join(users_list)}")
    else:
        menu.console.print(f"  [{colors['dim']}]No tunnel configured[/{colors['dim']}]")
    
    menu.console.print()
    menu.pause()


def complete(menu, text, tokens):
    """Command completion for info command"""
    opts = ['--raw', '-r']
    if len(tokens) <= 2:
        return [o for o in opts if o.startswith(text)]
    return []
