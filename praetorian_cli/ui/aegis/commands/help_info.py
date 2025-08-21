"""
Strongly-typed help information for commands.

This module provides a dataclass for command help information that ensures
consistent structure and provides type safety for help system.
"""

from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class CommandHelpInfo:
    """Strongly-typed help information for a command"""
    
    name: str
    description: str
    usage: str
    options: List[str] = field(default_factory=list)
    examples: List[str] = field(default_factory=list)
    notes: Optional[str] = None
    
    def __post_init__(self):
        """Validate required fields after initialization"""
        if not self.name:
            raise ValueError("Command name is required")
        if not self.description:
            raise ValueError("Command description is required") 
        if not self.usage:
            raise ValueError("Command usage is required")
    
    def has_options(self) -> bool:
        """Check if command has options"""
        return len(self.options) > 0
    
    def has_examples(self) -> bool:
        """Check if command has examples"""
        return len(self.examples) > 0
    
    def has_notes(self) -> bool:
        """Check if command has additional notes"""
        return self.notes is not None and len(self.notes.strip()) > 0
    
    def to_formatted_text(self, colors: dict = None) -> str:
        """
        Convert to formatted help text for display.
        
        Args:
            colors: Optional color configuration for Rich formatting
            
        Returns:
            Formatted help text string
        """
        colors = colors or {}
        accent = colors.get('accent', '')
        
        help_text = f"[bold]{self.description}[/bold]\n\nUsage: {self.usage}\n"
        
        if self.has_options():
            help_text += "\nOptions:\n"
            for option in self.options:
                help_text += f"  {option}\n"
        
        if self.has_examples():
            help_text += "\nExamples:\n"
            for example in self.examples:
                help_text += f"  {example}\n"
        
        if self.has_notes():
            help_text += f"\nNotes:\n{self.notes}\n"
        
        return help_text.strip()
    
    def get_summary(self) -> str:
        """Get a one-line summary for command listing"""
        return f"{self.name} - {self.description}"
    
    @classmethod
    def create_minimal(cls, name: str, description: str, usage: str = None) -> 'CommandHelpInfo':
        """
        Create minimal help info with just required fields.
        
        Args:
            name: Command name
            description: Command description  
            usage: Command usage (defaults to "name [options]")
            
        Returns:
            CommandHelpInfo instance
        """
        if usage is None:
            usage = f"{name} [options]"
        
        return cls(name=name, description=description, usage=usage)
    
    @classmethod
    def create_with_examples(cls, name: str, description: str, usage: str,
                           examples: List[str]) -> 'CommandHelpInfo':
        """
        Create help info with examples.
        
        Args:
            name: Command name
            description: Command description
            usage: Command usage
            examples: List of usage examples
            
        Returns:
            CommandHelpInfo instance with examples
        """
        return cls(name=name, description=description, usage=usage, examples=examples)