"""
Agent Menu Display
"""

from rich.panel import Panel
from rich.align import Align
from .style import AegisStyle


class AgentMenu:
    """Handle agent menu display and formatting"""
    
    def __init__(self, style: AegisStyle = None):
        self.style = style or AegisStyle()
        self.colors = self.style.colors
    
    def get_agent_header_panel(self, hostname: str) -> Panel:
        """Get the agent header panel"""
        agent_header = f"""[bold white]CHARIOT AGENT[/bold white] [dim white]│[/dim white] [bold {self.colors['accent']}]{hostname}[/bold {self.colors['accent']}]"""
        
        return Panel(
            Align.center(agent_header),
            style=f"bold white on {self.colors['dark_sec']}",
            border_style=self.colors['primary'],
            padding=(1, 2),
            title="[bold]AGENT[/bold]",
            title_align="left"
        )
    
    def get_actions_panel(self, shell_available: bool) -> Panel:
        """Get the actions panel for agent menu"""
        if shell_available:
            shell_action = f"[bold {self.colors['success']}]s[/bold {self.colors['success']}] → Connect to shell [dim](tunnel available)[/dim]"
        else:
            shell_action = f"[{self.colors['dim']}]s → Shell unavailable (no tunnel)[/{self.colors['dim']}]"
        
        actions_text = f"""[bold {self.colors['primary']}]Available Actions[/bold {self.colors['primary']}]

{shell_action}
[bold {self.colors['info']}]t[/bold {self.colors['info']}] → View and manage agent tasks
[bold {self.colors['secondary']}]i[/bold {self.colors['secondary']}] → Show detailed system information
[bold {self.colors['accent']}]b[/bold {self.colors['accent']}] → Return to main console"""
        
        return Panel(
            actions_text,
            border_style=self.colors['secondary'],
            padding=(1, 2),
            title="[dim]Actions[/dim]",
            title_align="left"
        )