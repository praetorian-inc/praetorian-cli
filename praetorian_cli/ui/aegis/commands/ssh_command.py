"""
SSH command for agent connections
"""

import subprocess
import time
from typing import List, Dict, Optional
from .base_command import BaseCommand


class SSHCommand(BaseCommand):
    """Handle SSH connections to agents"""
    
    def execute(self, args: List[str] = None):
        """Execute SSH command"""
        ssh_args = args or []
        self.handle_ssh_command(ssh_args)
    
    def handle_ssh_command(self, ssh_args=None):
        """Handle SSH command for selected agent with optional arguments"""
        if not self.selected_agent:
            self.console.print("\n  No agent selected. Use 'set <id>' to select one.\n")
            return
        
        # Check if SSH is available
        health = self.selected_agent.get('health_check', {})
        if not (health and health.get('cloudflared_status')):
            hostname = self.selected_agent.get('hostname', 'Unknown')
            self.console.print(f"\n  SSH not available for {hostname}")
            self.console.print(f"  [{self.colors['dim']}]This agent doesn't have an active tunnel[/{self.colors['dim']}]\n")
            return
        
        # Parse SSH arguments
        ssh_options = self.parse_ssh_args(ssh_args or [])
        if ssh_options is None:
            return  # Error in parsing, already displayed
        
        # Check if any SSH options were actually provided
        has_options = (
            ssh_options['local_forward'] or 
            ssh_options['remote_forward'] or 
            ssh_options['dynamic_forward'] or
            ssh_options['key'] or
            ssh_options['user']
        )
        
        if has_options:
            # Use the new options-based handler
            self.handle_shell_with_options(self.selected_agent, ssh_options)
        else:
            # Fall back to the original simple SSH handler
            self.handle_shell(self.selected_agent)
    
    def parse_ssh_args(self, args) -> Optional[Dict]:
        """Parse SSH command arguments and return options dict"""
        options = {
            'local_forward': [],
            'remote_forward': [],
            'dynamic_forward': None,
            'key': None,
            'ssh_opts': None,
            'user': None,
            'passthrough': []  # collect unknown flags to pass through
        }
        
        i = 0
        while i < len(args):
            arg = args[i]
            
            if arg in ['-L', '-l', '--local-forward']:
                if i + 1 >= len(args):
                    self.console.print("[red]Error: -L requires a port forwarding specification[/red]")
                    self.console.print("[dim]Example: ssh -L 8080:localhost:80[/dim]")
                    return None
                options['local_forward'].append(args[i + 1])
                i += 2
                
            elif arg in ['-R', '-r', '--remote-forward']:
                if i + 1 >= len(args):
                    self.console.print("[red]Error: -R requires a port forwarding specification[/red]")
                    self.console.print("[dim]Example: ssh -R 9090:localhost:3000[/dim]")
                    return None
                options['remote_forward'].append(args[i + 1])
                i += 2
                
            elif arg in ['-D', '-d', '--dynamic-forward']:
                if i + 1 >= len(args):
                    self.console.print("[red]Error: -D requires a port number[/red]")
                    self.console.print("[dim]Example: ssh -D 1080[/dim]")
                    return None
                try:
                    port = int(args[i + 1])
                    if port < 1 or port > 65535:
                        raise ValueError()
                    options['dynamic_forward'] = str(port)
                except ValueError:
                    self.console.print(f"[red]Error: Invalid port number '{args[i + 1]}'[/red]")
                    self.console.print("[dim]Port must be a number between 1 and 65535[/dim]")
                    return None
                i += 2
                
            elif arg in ['-i', '-I', '--key']:
                if i + 1 >= len(args):
                    self.console.print("[red]Error: -i requires a key file path[/red]")
                    self.console.print("[dim]Example: ssh -i ~/.ssh/my_key[/dim]")
                    self.pause()
                    return None
                options['key'] = args[i + 1]
                i += 2
                
            elif arg in ['-u', '-U', '--user']:
                if i + 1 >= len(args):
                    self.console.print("[red]Error: -u requires a username[/red]")
                    self.console.print("[dim]Example: ssh -u root[/dim]")
                    self.pause()
                    return None
                options['user'] = args[i + 1]
                i += 2
                
            elif arg.startswith('-'):
                # Collect unknown options and their arguments if any
                options['passthrough'].append(arg)
                # If next token is a value and current looks like expects arg (heuristic), include it
                if i + 1 < len(args) and not args[i + 1].startswith('-'):
                    options['passthrough'].append(args[i + 1])
                    i += 2
                else:
                    i += 1
            else:
                self.console.print(f"[red]Error: Unexpected argument '{arg}'[/red]")
                return None
            
        return options
    
    def handle_shell_with_options(self, agent, options):
        """Execute SSH command with the given options directly"""
        hostname = agent.get('hostname', 'unknown')
        
        # Check tunnel (same as original handle_shell)
        health = agent.get('health_check', {})
        if not (health and health.get('cloudflared_status')):
            self.console.print(f"[red]No Cloudflare tunnel available for {hostname}[/red]")
            return
        
        # Get tunnel information
        cf_status = health['cloudflared_status']
        public_hostname = cf_status.get('hostname')
        authorized_users = cf_status.get('authorized_users', '')
        tunnel_name = cf_status.get('tunnel_name', 'N/A')
        
        if not public_hostname:
            self.console.print(f"[red]No public hostname found in tunnel configuration for {hostname}[/red]")
            return
        
        # Determine SSH user
        ssh_user = options.get('user') or self.username
        
        # Minimal connection info
        self.console.print()
        self.console.print(f"  [{self.colors['success']}]Connecting to {hostname}[/{self.colors['success']}]")
        self.console.print(f"  [{self.colors['dim']}]via {public_hostname} • user: {ssh_user}[/{self.colors['dim']}]")
        
        # Show port forwarding if configured
        if options['local_forward']:
            for fwd in options['local_forward']:
                self.console.print(f"  [{self.colors['warning']}]Local forward: {fwd}[/{self.colors['warning']}]")
        
        if options['remote_forward']:
            for fwd in options['remote_forward']:
                self.console.print(f"  [{self.colors['warning']}]Remote forward: {fwd}[/{self.colors['warning']}]")
        
        if options['dynamic_forward']:
            self.console.print(f"  [{self.colors['warning']}]SOCKS proxy: port {options['dynamic_forward']}[/{self.colors['warning']}]")
        
        self.console.print(f"\n  [{self.colors['dim']}]Starting session... (Ctrl+C to exit)[/{self.colors['dim']}]")
        
        # Build SSH command directly (like original handle_shell)
        ssh_command = ['ssh']
        
        # Add SSH key if specified
        if options['key']:
            ssh_command.extend(['-i', options['key']])
        
        # Add local port forwarding (-L)
        for forward in options['local_forward']:
            ssh_command.extend(['-L', forward])
        
        # Add remote port forwarding (-R)
        for forward in options['remote_forward']:
            ssh_command.extend(['-R', forward])
        
        # Add dynamic port forwarding (-D)
        if options['dynamic_forward']:
            ssh_command.extend(['-D', options['dynamic_forward']])
        
        # Add passthrough options
        if options['passthrough']:
            ssh_command.extend(options['passthrough'])

        # Add the target
        ssh_command.append(f'{ssh_user}@{public_hostname}')
        
        try:
            # Give a moment for user to read the info
            time.sleep(1)
            
            # Execute SSH command with terminal interaction (like original handle_shell)
            result = subprocess.run(ssh_command)
            
            # After SSH session ends, return to menu
            self.console.print(f"\n[green]SSH session to {hostname} ended[/green]")
            
        except Exception as e:
            self.console.print(f"[red]Error executing SSH command: {e}[/red]")
    
    def handle_shell(self, agent: dict):
        """Handle simple shell connection without options"""
        hostname = agent.get('hostname', 'unknown')
        client_id = agent.get('client_id', 'N/A')
        
        # Check tunnel
        health = agent.get('health_check', {})
        if not (health and health.get('cloudflared_status')):
            self.console.print(f"[red]No Cloudflare tunnel available for {hostname}[/red]")
            self.pause()
            return
        
        # Get tunnel information
        cf_status = health['cloudflared_status']
        public_hostname = cf_status.get('hostname')
        authorized_users = cf_status.get('authorized_users', '')
        tunnel_name = cf_status.get('tunnel_name', 'N/A')
        
        if not public_hostname:
            self.console.print(f"[red]No public hostname found in tunnel configuration for {hostname}")
            self.pause()
            return
        
        # Minimal connection info for simple SSH
        self.console.print()
        self.console.print(f"  [{self.colors['success']}]Connecting to {hostname}[/{self.colors['success']}]")
        self.console.print(f"  [{self.colors['dim']}]via {public_hostname} • user: {self.username}[/{self.colors['dim']}]")
        
        if authorized_users:
            users_list = [u.strip() for u in authorized_users.split(',')]
            self.console.print(f"  [{self.colors['dim']}]authorized: {', '.join(users_list)}[/{self.colors['dim']}]")
        
        self.console.print(f"\n  [{self.colors['dim']}]Starting session... (Ctrl+C to exit)[/{self.colors['dim']}]")
        
        # Build SSH command using the current user's username
        ssh_command = ['ssh', f'{self.username}@{public_hostname}']
        
        try:
            # Give a moment for user to read the info
            time.sleep(1)
            
            # Execute SSH command with terminal interaction
            result = subprocess.run(ssh_command)
            
            # After SSH session ends, return to menu
            self.console.print(f"\n[green]SSH session to {hostname} ended[/green]")
            
        except KeyboardInterrupt:
            self.console.print(f"\n[yellow]SSH connection to {hostname} interrupted[/yellow]")
        except FileNotFoundError:
            self.console.print("\n[red]Error: SSH command not found. Please ensure SSH is installed.[/red]")
        except Exception as e:
            self.console.print(f"\n[red]SSH connection failed: {e}[/red]")
        
        self.pause()