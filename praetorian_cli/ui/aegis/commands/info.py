def handle_info(menu, args):
    """Show detailed information for the selected agent."""
    if not menu.selected_agent:
        menu.console.print("\n  No agent selected. Use 'set <id>' to select one.\n")
        menu.pause()
        return

    # Check for raw flag
    raw = ('--raw' in args) or ('-r' in args)
    
    try:
        _show_agent_info(menu, menu.selected_agent, raw=raw)
    except Exception as e:
        menu.console.print(f"[red]Error getting agent info: {e}[/red]")
        menu.pause()


def _show_agent_info(menu, agent, raw=False):
    """Show detailed agent info with clean formatting"""
    import json
    from datetime import datetime
    
    colors = getattr(menu, 'colors', {})
    hostname = agent.hostname or 'Unknown'
    
    # Clear screen and show header
    menu.clear_screen()
    menu.console.print()
    menu.console.print(f"  [{colors.get('primary', 'cyan')}]Agent Details[/{colors.get('primary', 'cyan')}]")
    menu.console.print()

    if raw:
        # Raw JSON dump with minimal styling
        menu.console.print(f"  [{colors.get('dim', 'dim')}]Raw agent data:[/{colors.get('dim', 'dim')}]")
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
    client_id = agent.client_id or 'N/A'
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
        is_online = (current_time - last_seen_seconds) < 60
        last_seen_str = datetime.fromtimestamp(last_seen_seconds).strftime("%Y-%m-%d %H:%M:%S")
        if is_online:
            status_text = f"[{colors.get('success', 'green')}]● online[/{colors.get('success', 'green')}]"
        else:
            status_text = f"[{colors.get('error', 'red')}]○ offline[/{colors.get('error', 'red')}]"
    else:
        last_seen_str = "never"
        status_text = f"[{colors.get('error', 'red')}]○ offline[/{colors.get('error', 'red')}]"
        is_online = False

    # Simple, clean output
    menu.console.print(f"  [bold white]{hostname}[/bold white]  {status_text}")
    menu.console.print(f"  [{colors.get('dim', 'dim')}]{fqdn}[/{colors.get('dim', 'dim')}]")
    menu.console.print()
    
    # System info
    menu.console.print(f"  [{colors.get('dim', 'dim')}]System[/{colors.get('dim', 'dim')}]")
    menu.console.print(f"    OS:           {os_info} {os_version}")
    menu.console.print(f"    Architecture: {architecture}")
    if ip_info:
        if len(ip_info) == 1:
            menu.console.print(f"    IP:           {ip_info[0]}")
        else:
            menu.console.print(f"    IPs:          {ip_info[0]}")
            for ip in ip_info[1:]:
                menu.console.print(f"                  {ip}")
    menu.console.print(f"    Client ID:    {client_id[:40]}...")
    menu.console.print(f"    Last seen:    {last_seen_str}")
    menu.console.print()
    
    # Tunnel info
    if cf_status:
        tunnel_name = cf_status.tunnel_name or 'N/A'
        public_hostname = cf_status.hostname or 'N/A'
        authorized_users = cf_status.authorized_users or ''
        
        menu.console.print(f"  [{colors.get('warning', 'yellow')}]Tunnel active[/{colors.get('warning', 'yellow')}]")
        menu.console.print(f"    Name:      {tunnel_name}")
        menu.console.print(f"    Public:    {public_hostname}")
        
        if authorized_users:
            users_list = [u.strip() for u in authorized_users.split(',')]
            menu.console.print(f"    Authorized: {', '.join(users_list)}")
    else:
        menu.console.print(f"  [{colors.get('dim', 'dim')}]No tunnel configured[/{colors.get('dim', 'dim')}]")
    
    menu.console.print()
    menu.pause()


def complete(menu, text, tokens):
    """Command completion for info command"""
    opts = ['--raw', '-r']
    if len(tokens) <= 2:
        return [o for o in opts if o.startswith(text)]
    return []
