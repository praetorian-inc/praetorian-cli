"""
Base completer class for Aegis command completion
"""

from abc import ABC, abstractmethod
from typing import List, Optional


class BaseCompleter(ABC):
    """Base class for all command completers"""
    
    def __init__(self, menu_instance):
        self.menu = menu_instance
        self.console = menu_instance.console
        self.style = menu_instance.style
        self.colors = menu_instance.colors
    
    @property
    def agents(self):
        """Get current agents list"""
        return self.menu.agents
    
    @property
    def selected_agent(self):
        """Get currently selected agent"""
        return self.menu.selected_agent
    
    @abstractmethod
    def get_completions(self, text: str, line: str, words: List[str]) -> List[str]:
        """Get completion suggestions for the given context"""
        pass
    
    def get_help_text(self, command: str, flag: Optional[str] = None) -> str:
        """Get help text for a command or flag"""
        _ = command, flag  # Suppress unused parameter warnings
        return ""
    
    def format_suggestion(self, suggestion: str, description: str = "") -> str:
        """Format a completion suggestion with indentation and description"""
        # Add indentation for better readability
        indent = "  "
        
        if description:
            # Use a clean format that readline can handle
            return f"{indent}{suggestion}  # {description}"
        
        return f"{indent}{suggestion}"
    
    def filter_suggestions(self, suggestions: List[str], text: str) -> List[str]:
        """Filter suggestions based on current input text"""
        if not text:
            return suggestions
        return [s for s in suggestions if s.startswith(text)]
    
    def get_common_ports(self) -> List[str]:
        """Get common port suggestions"""
        return ['22', '80', '443', '1080', '3389', '5432', '8080', '8443', '9050']
    
    def get_common_usernames(self) -> List[str]:
        """Get common username suggestions"""
        base_users = ['root', 'admin', 'administrator', 'user', 'ubuntu', 'ec2-user', 'centos']
        if hasattr(self.menu, 'username') and self.menu.username:
            base_users.insert(0, self.menu.username)
        return base_users