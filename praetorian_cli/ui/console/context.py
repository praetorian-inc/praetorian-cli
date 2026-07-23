import os
from dataclasses import dataclass, field
from typing import Optional, Dict, Any, List


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
    skills: List[str] = field(default_factory=list)

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

    def load_skill(self, path: str) -> str:
        """Load a skill file and add it to the active skills list. Returns the skill name."""
        resolved = os.path.realpath(os.path.expanduser(path))
        if not os.path.isfile(resolved):
            raise FileNotFoundError(f'Skill file not found: {path}')
        if resolved not in self.skills:
            self.skills.append(resolved)
        return os.path.basename(resolved)

    def unload_skill(self, path: str) -> bool:
        """Remove a skill from the active list. Returns True if found."""
        resolved = os.path.realpath(os.path.expanduser(path))
        if resolved in self.skills:
            self.skills.remove(resolved)
            return True
        # Try matching by basename
        for s in self.skills:
            if os.path.basename(s) == path:
                self.skills.remove(s)
                return True
        return False

    def apply_skills_to_message(self, message: str) -> str:
        """Prepend loaded skill file contents to a message."""
        if not self.skills:
            return message
        parts = []
        for path in self.skills:
            with open(path, 'r') as f:
                content = f.read()
            parts.append(f'<skill source="{os.path.basename(path)}">\n{content}\n</skill>')
        return '\n\n'.join(parts) + '\n\n' + message

    def apply_scope_to_message(self, message: str) -> str:
        """Prepend engagement scope context to a message for Marcus."""
        if self.scope:
            return f'Focus on assets matching {self.scope}. {message}'
        return message
