"""
Completion manager to coordinate all command completers
"""

import shlex
from typing import List, Dict, Any, Optional, Callable
from .ssh_completer import SSHCompleter
from .set_completer import SetCompleter


class CompletionManager:
    """Central coordinator for all command completers"""
    
    def __init__(self, menu_instance):
        self.menu = menu_instance
        self.console = menu_instance.console
        self.style = menu_instance.style
        self.colors = menu_instance.colors
        
        # Initialize command completers
        self.completers = {
            'ssh': SSHCompleter(menu_instance),
            'set': SetCompleter(menu_instance),
        }
        
        # Commands that support completion
        self.completable_commands = set(self.completers.keys())
        
        # All available commands for basic completion
        self.all_commands = [
            'set', 'ssh', 'info', 'list', 'reload', 'clear', 'help', 'quit', 'exit'
        ]
    
    def get_completions(self, text: str, line: str, begidx: int, endidx: int) -> List[str]:
        """Main completion entry point - called by readline"""
        try:
            # Parse the current line to understand context
            words = self._parse_line(line)
            
            # If no words or completing the first word, complete commands
            if not words or (len(words) == 1 and not line.endswith(' ')):
                return self._complete_commands(text)
            
            # Get the command being completed
            command = words[0].lower()
            
            # If we have a specific completer for this command, use it
            if command in self.completers:
                completer = self.completers[command]
                try:
                    completions = completer.get_completions(text, line, words)
                    return self._format_completions(completions, text)
                except Exception as e:
                    # Fallback to basic completion on error
                    self._debug_log(f"Completer error for {command}: {e}")
                    return []
            
            # No specific completer available
            return []
            
        except Exception as e:
            self._debug_log(f"Completion error: {e}")
            return []
    
    def _parse_line(self, line: str) -> List[str]:
        """Parse command line, handling quotes properly"""
        try:
            return shlex.split(line)
        except ValueError:
            # If shlex fails, fall back to simple split
            return line.split()
    
    def _complete_commands(self, text: str) -> List[str]:
        """Complete command names"""
        matches = []
        for cmd in self.all_commands:
            if cmd.startswith(text.lower()):
                # Add command with basic description
                desc = self._get_command_description(cmd)
                if desc:
                    matches.append(f"{cmd}  # {desc}")
                else:
                    matches.append(cmd)
        return matches
    
    def _get_command_description(self, command: str) -> str:
        """Get basic description for commands"""
        descriptions = {
            'set': 'Select an agent by number, client ID, or hostname',
            'ssh': 'Connect to selected agent via SSH with options',
            'info': 'Show detailed information about selected agent',
            'list': 'Display all available agents',
            'reload': 'Refresh agent list from server', 
            'clear': 'Clear the terminal screen',
            'help': 'Show help information',
            'quit': 'Exit Aegis console',
            'exit': 'Exit Aegis console'
        }
        return descriptions.get(command, '')
    
    def _format_completions(self, completions: List[str], text: str) -> List[str]:
        """Format completion suggestions"""
        if not completions:
            return []
        
        # Filter completions based on current text
        filtered = []
        for completion in completions:
            # Extract the actual completion value (before any # comment)
            actual_value = completion.split('  #')[0].strip()
            if actual_value.startswith(text) or not text:
                filtered.append(completion)
        
        # Sort completions for better UX
        return sorted(filtered)
    
    def get_help_text(self, command: str, flag: Optional[str] = None) -> str:
        """Get help text for a command or flag"""
        if command in self.completers:
            return self.completers[command].get_help_text(command, flag)
        
        return self._get_general_help()
    
    def _get_general_help(self) -> str:
        """Get general help text"""
        return f"""Aegis Commands:

{self.style.format_primary('Agent Management:')}
  set <id>         Select agent by number, client ID, or hostname
  info             Show detailed info for selected agent  
  list             Display all available agents
  reload           Refresh agent list from server

{self.style.format_success('Connectivity:')}
  ssh [options]    Connect to selected agent via SSH
  
{self.style.format_accent('System:')}
  clear            Clear terminal screen
  help             Show this help
  quit/exit        Exit Aegis

{self.style.format_dim('Tips:')}
• Use TAB for command and argument completion
• Type command + --help for detailed usage
• Commands support intelligent autocompletion"""
    
    def validate_command(self, command: str, args: List[str]) -> bool:
        """Validate a command and its arguments"""
        if command not in self.all_commands:
            return False
        
        # Use specific validator if available
        if command in self.completers:
            completer = self.completers[command]
            if hasattr(completer, 'validate_args'):
                return completer.validate_args(args)
        
        return True
    
    def get_command_suggestions(self, partial_command: str) -> List[str]:
        """Get command suggestions for partial input"""
        suggestions = []
        for cmd in self.all_commands:
            if cmd.startswith(partial_command.lower()):
                suggestions.append(cmd)
        return suggestions
    
    def _debug_log(self, message: str):
        """Debug logging (can be expanded)"""
        # For now, just pass - could log to file in debug mode
        pass
    
    def refresh_completions(self):
        """Refresh completion data (e.g., when agents list changes)"""
        # This can be called when agents are reloaded
        for completer in self.completers.values():
            if hasattr(completer, 'refresh'):
                try:
                    completer.refresh()
                except Exception as e:
                    self._debug_log(f"Error refreshing completer: {e}")
    
    def register_completer(self, command: str, completer_class):
        """Register a new command completer"""
        try:
            self.completers[command] = completer_class(self.menu)
            self.completable_commands.add(command)
            if command not in self.all_commands:
                self.all_commands.append(command)
        except Exception as e:
            self._debug_log(f"Error registering completer for {command}: {e}")
    
    def get_completion_statistics(self) -> Dict[str, Any]:
        """Get statistics about completion usage"""
        return {
            'total_commands': len(self.all_commands),
            'completable_commands': len(self.completable_commands),
            'registered_completers': list(self.completers.keys()),
            'agents_count': len(self.menu.agents) if hasattr(self.menu, 'agents') else 0
        }