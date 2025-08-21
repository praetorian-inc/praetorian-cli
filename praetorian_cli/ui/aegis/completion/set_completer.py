"""
SET command completer for agent selection
"""

from typing import List, Dict, Any, Optional
from .base_completer import BaseCompleter


class SetCompleter(BaseCompleter):
    """Completer for SET command with agent selection support"""
    
    def __init__(self, menu_instance):
        super().__init__(menu_instance)
    
    def get_completions(self, text: str, line: str, words: List[str]) -> List[str]:
        """Get SET command completions for agent selection"""
        # SET command expects exactly one argument (agent identifier)
        # Handle both "set " and "set partial_text" cases
        if len(words) == 1 and line.endswith(' '):
            # Case: "set " - show all available agents  
            return self._complete_agent_identifiers("")
        elif len(words) == 2:
            # Case: "set something" - complete the partial text
            return self._complete_agent_identifiers(text)
        elif len(words) < 1:
            # Invalid state
            return []
        
        # No more completions after agent identifier
        return []
    
    def _complete_agent_identifiers(self, text: str) -> List[str]:
        """Complete agent identifiers in format: {NUMERIC} - {HOSTNAME} - {OS}"""
        if not self.agents:
            return [f"# No agents available - use 'reload' to refresh"]
        
        suggestions = []
        
        for i, agent in enumerate(self.agents, 1):
            agent_num = str(i)
            hostname = getattr(agent, 'hostname', 'Unknown')
            client_id = getattr(agent, 'client_id', 'Unknown')
            os_info = getattr(agent, 'os', 'unknown').title()
            
            # Create the combined format: {NUMERIC} - {HOSTNAME} - {OS}
            combined_format = f"{agent_num} - {hostname} - {os_info}"
            
            # Check if this agent matches the text
            matches = False
            
            # Check if text matches any identifier
            if not text:  # Empty text - show all agents
                matches = True
            elif agent_num.startswith(text):  # Numeric match
                matches = True
            elif client_id and client_id != 'Unknown' and client_id.lower().startswith(text.lower()):  # Client ID match
                matches = True
            elif hostname and hostname != 'Unknown' and hostname.lower().startswith(text.lower()):  # Hostname match
                matches = True
            elif combined_format.lower().find(text.lower()) != -1:  # Text appears anywhere in combined format
                matches = True
            
            if matches:
                # Add additional context in the description
                desc = f"Client ID: {client_id[:12]}... | {self._format_last_seen(agent)}"
                suggestion = self.format_suggestion(combined_format, desc)
                suggestions.append(suggestion)
        
        return suggestions
    
    def _format_last_seen(self, agent) -> str:
        """Format last seen information for display"""
        last_seen_at = getattr(agent, 'last_seen_at', 0)
        if not last_seen_at:
            return "Never seen"
        
        # Use the is_online property from the Agent class
        status_text = "Online" if agent.is_online else "Offline"
        return f"{status_text}"
    
    def get_agent_suggestions_by_type(self) -> Dict[str, List[Dict[str, Any]]]:
        """Get agent suggestions with combined ID and hostname information"""
        if not self.agents:
            return {'combined': []}
        
        suggestions = {
            'combined': []
        }
        
        for i, agent in enumerate(self.agents, 1):
            hostname = getattr(agent, 'hostname', 'Unknown')
            client_id = getattr(agent, 'client_id', 'Unknown')
            os_info = getattr(agent, 'os', 'unknown').title()
            status = self._get_agent_status(agent)
            
            # Create combined suggestion with multiple access patterns
            agent_suggestion = {
                'agent_number': str(i),
                'hostname': hostname,
                'client_id': client_id,
                'display_name': f"{i} - {hostname} ({client_id[:8]}...)",
                'os': os_info,
                'status': status,
                'description': f"{hostname} - {os_info} - {status}"
            }
            suggestions['combined'].append(agent_suggestion)
        
        return suggestions
    
    def _get_agent_status(self, agent: dict) -> str:
        """Get agent status string"""
        if 'computed_status' in agent:
            status_obj = agent['computed_status']
            if hasattr(status_obj, 'plain'):
                return status_obj.plain
            return str(status_obj)
        return "Unknown"
    
    def get_help_text(self, command: str, flag: Optional[str] = None) -> str:
        """Get help text for SET command"""
        agent_count = len(self.agents)
        
        help_text = f"""SET Command - Select Active Agent

Usage: set <agent_identifier>

Agent Identifiers ({agent_count} agents available):
  • Agent Number    : 1, 2, 3, ... {agent_count}
  • Client ID       : Full client ID (e.g., C.abc123def456...)
  • Hostname        : Agent hostname (e.g., kali-box, ubuntu-server)

Examples:
  set 1              # Select first agent
  set C.abc123       # Select by client ID  
  set kali-box       # Select by hostname

Current Selection:"""
        
        if self.selected_agent:
            hostname = self.selected_agent.get('hostname', 'Unknown')
            client_id = self.selected_agent.get('client_id', 'Unknown')
            help_text += f"\n  ✓ {hostname} ({client_id})"
        else:
            help_text += "\n  ✗ No agent selected"
        
        if agent_count == 0:
            help_text += "\n\nNo agents available. Use 'reload' to refresh the agent list."
        
        return help_text
    
    def validate_agent_identifier(self, identifier: str) -> Optional[Dict[str, Any]]:
        """Validate and return agent info for an identifier"""
        if not self.agents:
            return None
        
        # Try numeric index first
        if identifier.isdigit():
            agent_num = int(identifier)
            if 1 <= agent_num <= len(self.agents):
                return self.agents[agent_num - 1]
        
        # Try client ID match
        for agent in self.agents:
            if agent.get('client_id', '').lower() == identifier.lower():
                return agent
        
        # Try hostname match  
        for agent in self.agents:
            if agent.get('hostname', '').lower() == identifier.lower():
                return agent
        
        return None