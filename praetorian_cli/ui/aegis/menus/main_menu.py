"""
Main Menu Display
"""

from rich.panel import Panel
from rich.align import Align
from .style import AegisStyle


class MainMenu:
    """Handle main menu display and formatting"""
    
    def __init__(self, style: AegisStyle = None):
        self.style = style or AegisStyle()
        self.colors = self.style.colors
    
    def get_header_panel(self, user_email: str, username: str, current_account: str = None) -> Panel:
        """Get the main header panel"""
        if current_account and current_account != user_email:
            # Show both user and account if they're different (assumed role)
            user_info = f"User: {user_email} • Account: {current_account} • SSH as: {username}"
        else:
            # Show just user and SSH username if no assumed role
            user_info = f"User: {user_email} • SSH as: {username}"
            
        header_content = f"""[bold white]CHARIOT AEGIS[/bold white] [dim white]│[/dim white] [bold {self.colors['accent']}]Interactive Console[/bold {self.colors['accent']}]
[dim {self.colors['dim']}]Unified Agent Management • Direct SSH Access • Real-time Operations[/dim {self.colors['dim']}]
[dim {self.colors['dim']}]{user_info}[/dim {self.colors['dim']}]"""
        
        return Panel(
            Align.center(header_content),
            style=f"bold white on {self.colors['dark_sec']}",
            border_style=self.colors['primary'],
            padding=(1, 2),
            title="[bold]CHARIOT[/bold]",
            title_align="left"
        )
    
    def get_selected_agent_info(self, selected_agent=None) -> str:
        """Get selected agent information text"""
        if selected_agent:
            hostname = selected_agent.get('hostname', 'Unknown')
            client_id = selected_agent.get('client_id', 'Unknown')
            return f"[bold {self.colors['success']}]Selected Agent:[/bold {self.colors['success']}] {hostname} ({client_id})"
        else:
            return f"[{self.colors['dim']}]No agent selected - use 'set <id>' to choose an agent[/{self.colors['dim']}]"
    
    def get_commands_panel(self, ssh_count: int, total_agents: int, selected_info: str) -> Panel:
        """Get the commands reference panel"""
        cmd_text = f"""[bold {self.colors['primary']}]Available Commands[/bold {self.colors['primary']}] [dim]({ssh_count}/{total_agents} agents have SSH capability)[/dim]
{selected_info}

[bold {self.colors['success']}]🔗 Agent Selection & Actions:[/bold {self.colors['success']}]
  [bold {self.colors['success']}]set <id>[/bold {self.colors['success']}] → Set current agent by number, client ID, or hostname
  [bold {self.colors['success']}]ssh [options][/bold {self.colors['success']}] → Connect to selected agent via SSH
  [bold {self.colors['info']}]info[/bold {self.colors['info']}] → Show detailed information for selected agent
  
[bold {self.colors['accent']}]System Commands:[/bold {self.colors['accent']}]
  [bold]list[/bold] → Show all agents    [bold {self.colors['warning']}]reload[/bold {self.colors['warning']}] → Refresh agent list
  [bold]clear[/bold] → Clear screen    [bold]help[/bold] → Show this help    [bold {self.colors['error']}]quit[/bold {self.colors['error']}] → Exit

[dim]💡 Tips: Use TAB for auto-completion • Type 'set 1' or 'ssh -D 1080' for SOCKS proxy[/dim]"""
        
        return Panel(
            cmd_text,
            border_style=self.colors['accent'],
            padding=(1, 2),
            title="[dim]Commands[/dim]",
            title_align="left"
        )