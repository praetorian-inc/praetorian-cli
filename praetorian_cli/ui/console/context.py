from dataclasses import dataclass, field
from typing import Optional, Dict, Any


@dataclass
class EngagementContext:
    """Tracks the current engagement state for the interactive console."""
    account: Optional[str] = None
    scope: Optional[str] = None
    conversation_id: Optional[str] = None
    mode: str = 'agent'
    active_agent: Optional[str] = None
    # Metasploit-style "use" state
    active_tool: Optional[str] = None
    active_tool_config: Optional[Dict[str, Any]] = None
    target: Optional[str] = None
    verbose: bool = False

    def clear_conversation(self):
        self.conversation_id = None
        self.active_agent = None

    def clear_tool(self):
        self.active_tool = None
        self.active_tool_config = None
        self.target = None

    def summary(self) -> str:
        parts = []
        parts.append(f'account: {self.account or "none"}')
        if self.scope:
            parts.append(f'scope: {self.scope}')
        if self.active_tool:
            parts.append(f'tool: {self.active_tool}')
        if self.target:
            parts.append(f'target: {self.target}')
        parts.append(f'mode: {self.mode}')
        if self.active_agent:
            parts.append(f'agent: {self.active_agent}')
        return ' | '.join(parts)

    def apply_scope_to_message(self, message: str) -> str:
        """Prepend engagement scope context to a message for Marcus."""
        if self.scope:
            return f'Focus on assets matching {self.scope}. {message}'
        return message
