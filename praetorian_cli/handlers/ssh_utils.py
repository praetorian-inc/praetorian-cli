"""
Shared SSH utilities for Aegis CLI and TUI commands
"""

from typing import List, Dict, Optional
from praetorian_cli.sdk.model.aegis import validate_agent_for_ssh


class SSHArgumentParser:
    """Shared SSH argument parser for both CLI and TUI interfaces"""
    
    def __init__(self, console=None):
        self.console = console
    
    def parse_ssh_args(self, args: List[str]) -> Optional[Dict]:
        """
        Parse SSH command arguments and return options dict
        Returns None if parsing fails with error messages displayed
        """
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
            
            if arg in ['-L', '--local-forward']:
                if i + 1 >= len(args):
                    self._print_error("Error: -L requires a port forwarding specification")
                    self._print_error("Example: ssh -L 8080:localhost:80", dim=True)
                    return None
                options['local_forward'].append(args[i + 1])
                i += 2

            elif arg.startswith('--local-forward='):
                options['local_forward'].append(arg.split('=', 1)[1])
                i += 1

            elif arg in ['-l', '--login-name']:
                if i + 1 >= len(args):
                    self._print_error("Error: -l requires a username")
                    self._print_error("Example: ssh -l root", dim=True)
                    return None
                options['user'] = args[i + 1]
                i += 2

            elif arg.startswith('-l') and len(arg) > 2:
                options['user'] = arg[2:]
                i += 1
                
            elif arg in ['-R', '-r', '--remote-forward']:
                if i + 1 >= len(args):
                    self._print_error("Error: -R requires a port forwarding specification")
                    self._print_error("Example: ssh -R 9090:localhost:3000", dim=True)
                    return None
                options['remote_forward'].append(args[i + 1])
                i += 2
                
            elif arg in ['-D', '-d', '--dynamic-forward']:
                if i + 1 >= len(args):
                    self._print_error("Error: -D requires a port number")
                    self._print_error("Example: ssh -D 1080", dim=True)
                    return None
                try:
                    port = int(args[i + 1])
                    if port < 1 or port > 65535:
                        raise ValueError()
                    options['dynamic_forward'] = str(port)
                except ValueError:
                    self._print_error(f"Error: Invalid port number '{args[i + 1]}'")
                    self._print_error("Port must be a number between 1 and 65535", dim=True)
                    return None
                i += 2
                
            elif arg in ['-i', '-I', '--key']:
                if i + 1 >= len(args):
                    self._print_error("Error: -i requires a key file path")
                    self._print_error("Example: ssh -i ~/.ssh/my_key", dim=True)
                    return None
                options['key'] = args[i + 1]
                i += 2
                
            elif arg in ['-u', '-U', '--user']:
                if i + 1 >= len(args):
                    self._print_error("Error: -u requires a username")
                    self._print_error("Example: ssh -u root", dim=True)
                    return None
                options['user'] = args[i + 1]
                i += 2

            elif arg.startswith('--user='):
                options['user'] = arg.split('=', 1)[1]
                i += 1
                
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
                self._print_error(f"Error: Unexpected argument '{arg}'")
                return None
            
        return options
    
    def validate_agent_ssh_availability(self, agent) -> bool:
        """
        Check if SSH is available for the given agent
        Returns True if available, False otherwise with error messages displayed
        """
        is_valid, error_msg = validate_agent_for_ssh(agent)
        if not is_valid:
            self._print_error(error_msg)
            return False
        return True
    
    def has_ssh_options(self, options: Dict) -> bool:
        """Check if any actual SSH options were provided (not just passthrough)"""
        return bool(
            options['local_forward'] or 
            options['remote_forward'] or 
            options['dynamic_forward'] or
            options['key'] or
            options['user']
        )
    
    def _print_error(self, message: str, dim: bool = False):
        """Print error message using console if available, otherwise plain print"""
        if self.console:
            if dim:
                self.console.print(f"[dim]{message}[/dim]")
            else:
                self.console.print(f"[red]{message}[/red]")
        else:
            # Fallback for CLI usage
            print(f"Error: {message}" if not dim else message)
