"""
Aegis Style Management
"""


class AegisStyle:
    """Professional Praetorian color scheme and styling constants"""
    
    def __init__(self):
        # Professional Praetorian color scheme
        self.colors = {
            'primary': '#5F47B7',      # Primary purple
            'secondary': '#8F7ECD',    # Secondary purple  
            'accent': '#BFB5E2',       # Tertiary purple
            'dark': '#0D0D28',         # Dark primary
            'dark_sec': '#191933',     # Dark secondary
            'success': '#4CAF50',      # Green
            'error': '#F44336',        # Red
            'warning': '#FFC107',      # Yellow
            'info': '#2196F3',         # Blue
            'text': '#FFFFFF',         # White text
            'dim': '#B6B6BE'           # Light secondary
        }
    
    def get_color(self, color_name: str) -> str:
        """Get color by name"""
        return self.colors.get(color_name, '#FFFFFF')
    
    def format_success(self, text: str) -> str:
        """Format text with success color"""
        return f"[{self.colors['success']}]{text}[/{self.colors['success']}]"
    
    def format_error(self, text: str) -> str:
        """Format text with error color"""
        return f"[{self.colors['error']}]{text}[/{self.colors['error']}]"
    
    def format_warning(self, text: str) -> str:
        """Format text with warning color"""
        return f"[{self.colors['warning']}]{text}[/{self.colors['warning']}]"
    
    def format_info(self, text: str) -> str:
        """Format text with info color"""
        return f"[{self.colors['info']}]{text}[/{self.colors['info']}]"
    
    def format_dim(self, text: str) -> str:
        """Format text with dim color"""
        return f"[{self.colors['dim']}]{text}[/{self.colors['dim']}]"
    
    def format_primary(self, text: str) -> str:
        """Format text with primary color"""
        return f"[{self.colors['primary']}]{text}[/{self.colors['primary']}]"
    
    def format_accent(self, text: str) -> str:
        """Format text with accent color"""
        return f"[{self.colors['accent']}]{text}[/{self.colors['accent']}]"