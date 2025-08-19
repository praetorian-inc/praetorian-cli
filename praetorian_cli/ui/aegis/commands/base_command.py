"""
Base command class for Aegis commands
"""

from abc import ABC, abstractmethod
from typing import List


class BaseCommand(ABC):
    """Base class for all Aegis commands"""
    
    def __init__(self, menu):
        """Initialize command with reference to the menu instance"""
        self.menu = menu
        self.console = menu.console
        self.sdk = menu.sdk
        self.colors = menu.colors
    
    @property 
    def agents(self):
        """Get agents list from menu"""
        return self.menu.agents
    
    @property
    def selected_agent(self):
        """Get selected agent from menu"""
        return self.menu.selected_agent
    
    @selected_agent.setter
    def selected_agent(self, agent):
        """Set selected agent in menu"""
        self.menu.selected_agent = agent
    
    @property
    def username(self):
        """Get username from menu"""
        return self.menu.username
    
    def pause(self):
        """Pause for user input"""
        self.menu.pause()
    
    def clear_screen(self):
        """Clear screen"""
        self.menu.clear_screen()
    
    def get_agent_context(self):
        """Get the full agent context from menu"""
        return self.menu.get_selected_agent_context()
    
    def require_selected_agent(self):
        """Return selected agent or display error and return None"""
        return self.menu.require_selected_agent()
    
    def has_selected_agent(self):
        """Check if an agent is currently selected"""
        return self.menu.has_selected_agent()
    
    def call_sdk_with_agent(self, method_path, *args, **kwargs):
        """Call SDK method using the selected agent context"""
        return self.menu.call_sdk_with_agent(method_path, *args, **kwargs)
    
    @abstractmethod
    def execute(self, args: List[str] = None):
        """Execute the command with given arguments"""
        pass