"""
SSH command completer with comprehensive option support
"""

import os
from typing import List, Dict, Any, Optional
from .base_completer import BaseCompleter


class SSHCompleter(BaseCompleter):
    """Comprehensive SSH command completer based on SSH man page"""
    
    def __init__(self, menu_instance):
        super().__init__(menu_instance)
        
        # SSH options from man page with descriptions
        self.ssh_options = {
            # Authentication & Identity
            '-i': {
                'arg': 'identity_file',
                'desc': 'Private key file for public key authentication',
                'type': 'file',
                'example': '~/.ssh/id_rsa'
            },
            '-l': {
                'arg': 'login_name', 
                'desc': 'User to log in as on remote machine',
                'type': 'username',
                'example': 'root'
            },
            '-A': {
                'arg': None,
                'desc': 'Enable authentication agent forwarding',
                'type': 'flag'
            },
            '-a': {
                'arg': None,
                'desc': 'Disable authentication agent forwarding', 
                'type': 'flag'
            },
            
            # Port Forwarding
            '-L': {
                'arg': '[bind_address:]port:host:hostport',
                'desc': 'Local port forwarding',
                'type': 'port_forward',
                'example': '8080:localhost:80'
            },
            '-R': {
                'arg': '[bind_address:]port:host:hostport',
                'desc': 'Remote port forwarding',
                'type': 'port_forward', 
                'example': '9090:localhost:3000'
            },
            '-D': {
                'arg': '[bind_address:]port',
                'desc': 'SOCKS proxy (dynamic forwarding)',
                'type': 'port',
                'example': '1080'
            },
            
            # Connection Control
            '-p': {
                'arg': 'port',
                'desc': 'Port to connect to on remote host',
                'type': 'port',
                'example': '22'
            },
            '-4': {
                'arg': None,
                'desc': 'Force IPv4 addresses only',
                'type': 'flag'
            },
            '-6': {
                'arg': None,
                'desc': 'Force IPv6 addresses only', 
                'type': 'flag'
            },
            '-N': {
                'arg': None,
                'desc': "Don't execute remote command (port forwarding only)",
                'type': 'flag'
            },
            '-T': {
                'arg': None,
                'desc': 'Disable pseudo-terminal allocation',
                'type': 'flag'
            },
            '-t': {
                'arg': None,
                'desc': 'Force pseudo-terminal allocation',
                'type': 'flag'
            },
            '-f': {
                'arg': None,
                'desc': 'Background SSH before command execution',
                'type': 'flag'
            },
            
            # Other Useful Options
            '-C': {
                'arg': None,
                'desc': 'Request compression of all data',
                'type': 'flag'
            },
            '-v': {
                'arg': None,
                'desc': 'Verbose mode (debugging messages)',
                'type': 'flag'
            },
            '-q': {
                'arg': None,
                'desc': 'Quiet mode (suppress warnings)',
                'type': 'flag'
            },
            '-F': {
                'arg': 'config_file',
                'desc': 'Alternative configuration file',
                'type': 'file',
                'example': '~/.ssh/config'
            },
            '-o': {
                'arg': 'option',
                'desc': 'Configuration options',
                'type': 'option',
                'example': 'StrictHostKeyChecking=no'
            },
            '-J': {
                'arg': 'destination',
                'desc': 'Connect via jump host',
                'type': 'hostname',
                'example': 'jumphost.example.com'
            },
            '-B': {
                'arg': 'bind_interface',
                'desc': 'Bind to specific network interface',
                'type': 'interface',
                'example': 'eth0'
            },
            '-E': {
                'arg': 'log_file',
                'desc': 'Append debug logs to file',
                'type': 'file',
                'example': '/tmp/ssh.log'
            }
        }
        
        # Value suggestions for different argument types
        self.value_suggestions = {
            'port': ['22', '80', '443', '1080', '2222', '3389', '8022', '8080', '8443', '9050'],
            'port_forward': [
                '8080:localhost:80',
                '3389:target:3389', 
                '5432:database:5432',
                '3306:mysql:3306',
                '443:webserver:443',
                '9090:localhost:9000'
            ],
            'username': self.get_common_usernames(),
            'option': [
                'StrictHostKeyChecking=no',
                'UserKnownHostsFile=/dev/null',
                'PasswordAuthentication=no',
                'PubkeyAuthentication=yes',
                'ConnectTimeout=30',
                'ServerAliveInterval=60',
                'ServerAliveCountMax=3',
                'ForwardX11=yes',
                'ForwardAgent=yes',
                'Compression=yes'
            ]
        }
    
    def get_completions(self, text: str, line: str, words: List[str]) -> List[str]:
        """Get SSH command completions"""
        if len(words) <= 1:
            return []
        
        # Remove 'ssh' command from words for analysis
        ssh_args = words[1:]
        
        # If text starts with -, complete SSH options
        if text.startswith('-'):
            return self._complete_ssh_options(text)
        
        # Check if we need to complete a value for the previous option
        if len(ssh_args) >= 1:
            # If we're completing after a space, look at the last argument
            if not text and ssh_args:
                prev_arg = ssh_args[-1]
            # If we're completing a partial word, look at the previous argument
            elif len(ssh_args) >= 2:
                prev_arg = ssh_args[-2]
            else:
                prev_arg = None
                
            if prev_arg and prev_arg in self.ssh_options:
                option_info = self.ssh_options[prev_arg]
                if option_info['arg'] is not None:  # Option expects an argument
                    return self._complete_option_value(prev_arg, text)
        
        # If no specific completion context, show available options
        if not text or text.startswith('-'):
            return self._complete_ssh_options(text)
        
        return []
    
    def _complete_ssh_options(self, text: str) -> List[str]:
        """Complete SSH option flags"""
        matches = []
        for option, info in self.ssh_options.items():
            if option.startswith(text):
                desc = info['desc']
                if info['arg']:
                    formatted = f"{option} {info['arg']}  # {desc}"
                else:
                    formatted = f"{option}  # {desc}"
                matches.append(formatted)
        return matches
    
    def _complete_option_value(self, option: str, text: str) -> List[str]:
        """Complete values for SSH options"""
        if option not in self.ssh_options:
            return []
        
        option_info = self.ssh_options[option]
        value_type = option_info['type']
        
        # Get suggestions based on value type
        suggestions = []
        
        if value_type in self.value_suggestions:
            suggestions = self.value_suggestions[value_type].copy()
        
        # Add example if available
        if 'example' in option_info:
            example = option_info['example']
            if example not in suggestions:
                suggestions.insert(0, example)
        
        # Special handling for file paths
        if value_type == 'file':
            suggestions.extend(self._get_file_completions(text))
        
        # Filter and return matches
        return self.filter_suggestions(suggestions, text)
    
    def _get_file_completions(self, text: str) -> List[str]:
        """Get file path completions, especially for SSH keys"""
        suggestions = []
        
        # Common SSH key locations
        ssh_dir = os.path.expanduser('~/.ssh')
        if os.path.exists(ssh_dir):
            try:
                for file in os.listdir(ssh_dir):
                    if not file.startswith('.') and not file.endswith('.pub'):
                        full_path = f"~/.ssh/{file}"
                        if full_path.startswith(text) or not text:
                            suggestions.append(full_path)
            except (OSError, PermissionError):
                pass
        
        # Add common paths
        common_paths = [
            '~/.ssh/id_rsa',
            '~/.ssh/id_ecdsa', 
            '~/.ssh/id_ed25519',
            '~/.ssh/config'
        ]
        
        for path in common_paths:
            if path.startswith(text) or not text:
                suggestions.append(path)
        
        return suggestions
    
    def get_help_text(self, command: str, flag: Optional[str] = None) -> str:
        """Get help text for SSH command or specific flag"""
        if flag and flag in self.ssh_options:
            option_info = self.ssh_options[flag]
            help_text = f"{flag}"
            if option_info['arg']:
                help_text += f" {option_info['arg']}"
            help_text += f"\n  {option_info['desc']}"
            if 'example' in option_info:
                help_text += f"\n  Example: {flag} {option_info['example']}"
            return help_text
        
        # General SSH help
        return """SSH Command Options:
        
Authentication:
  -i identity_file    Private key for authentication
  -l login_name      User to log in as
  -A                 Enable agent forwarding
  
Port Forwarding:
  -L port:host:port  Local port forwarding  
  -R port:host:port  Remote port forwarding
  -D port            SOCKS proxy
  
Connection:
  -p port            Remote port (default: 22)
  -4/-6              Force IPv4/IPv6
  -N                 No remote command
  -f                 Background execution
  
Other:
  -v                 Verbose mode
  -C                 Enable compression
  -F config          Config file
  -o option          SSH options
  
Use 'ssh -<flag> --help' for detailed flag information."""