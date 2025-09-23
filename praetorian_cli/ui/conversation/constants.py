"""
Constants for the conversation TUI interface
"""

# Default color scheme
DEFAULT_COLORS = {
    'primary': 'cyan',
    'accent': 'bright_cyan', 
    'success': 'green',
    'warning': 'yellow',
    'error': 'red',
    'dim': 'bright_black',
    'user': 'blue',
    'ai': 'green',
    'tool': 'yellow',
    'system': 'magenta'
}

# Message role mappings
ROLE_DISPLAY = {
    'user': '👤 User',
    'chariot': '🤖 AI',
    'system': '⚙️  System',
    'tool call': '🔧 Tool Call',
    'tool response': '📊 Tool Result'
}

# Tool call summaries for common tools
TOOL_SUMMARIES = {
    'query': 'Searched security database',
    'job': 'Started security scan',
    'capabilities': 'Listed available capabilities'
}