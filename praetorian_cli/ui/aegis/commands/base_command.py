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
    
    @abstractmethod
    def execute(self, args: List[str] = None):
        """Execute the command with given arguments"""
        pass