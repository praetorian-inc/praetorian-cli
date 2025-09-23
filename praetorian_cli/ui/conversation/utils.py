"""
Utility functions for the conversation TUI interface
"""

import json
from datetime import datetime
from typing import Dict, Any
from rich.text import Text
from rich.markdown import Markdown
from rich.panel import Panel
from .constants import ROLE_DISPLAY, TOOL_SUMMARIES


def format_timestamp(timestamp: str) -> str:
    """Format timestamp for display"""
    if not timestamp:
        return ""
    
    try:
        # Try parsing ISO format
        if 'T' in timestamp:
            dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
        else:
            # Try parsing as unix timestamp
            dt = datetime.fromtimestamp(float(timestamp))
            
        # Return relative time
        now = datetime.now(dt.tzinfo) if dt.tzinfo else datetime.now()
        diff = now - dt
        
        if diff.days > 0:
            return f"{diff.days}d ago"
        elif diff.seconds > 3600:
            hours = diff.seconds // 3600
            return f"{hours}h ago"
        elif diff.seconds > 60:
            minutes = diff.seconds // 60
            return f"{minutes}m ago"
        else:
            return "now"
            
    except (ValueError, TypeError):
        return timestamp[:10]  # Return first 10 chars if parsing fails


def format_message_role(role: str, colors: Dict[str, str]) -> Text:
    """Format message role for display"""
    role_text = ROLE_DISPLAY.get(role, f"• {role.title()}")
    
    if role == 'user':
        return Text(role_text, style=f"bold {colors['user']}")
    elif role == 'chariot':
        return Text(role_text, style=f"bold {colors['ai']}")
    elif role in ['tool call', 'tool response']:
        return Text(role_text, style=f"bold {colors['tool']}")
    else:
        return Text(role_text, style=f"bold {colors['system']}")


def parse_message_content(role: str, content: str, colors: Dict[str, str]) -> Any:
    """Parse and format message content based on role"""
    
    if role == 'user':
        # User messages - simple text
        return Text(f"  {content}", style="white")
    
    elif role == 'chariot':
        # AI responses - render as markdown for formatting
        try:
            return Markdown(f"  {content}")
        except Exception:
            return Text(f"  {content}", style="white")
    
    elif role == 'tool call':
        # Tool calls - show brief summary instead of full JSON
        try:
            if content.startswith('{'):
                tool_data = json.loads(content)
                tool_name = tool_data.get('name', 'unknown')
                summary = TOOL_SUMMARIES.get(tool_name, f"Called {tool_name} tool")
                
                # Show brief summary in a styled panel
                return Panel(
                    Text(summary, style=colors['tool']),
                    border_style=colors['dim'],
                    padding=(0, 1),
                    title=f"[{colors['dim']}]Tool Call[/{colors['dim']}]",
                    title_align="left"
                )
            else:
                return Text(f"  {content}", style=colors['dim'])
        except json.JSONDecodeError:
            return Text(f"  {content[:100]}...", style=colors['dim'])
    
    elif role == 'tool response':
        # Tool responses - show summary instead of full data
        try:
            if content.startswith('{'):
                result_data = json.loads(content)
                
                # Format different types of tool results
                if 'capabilities' in result_data:
                    count = result_data.get('count', len(result_data.get('capabilities', [])))
                    summary = f"Found {count} security capabilities"
                elif 'jobs' in result_data:
                    jobs = result_data.get('jobs', [])
                    count = len(jobs) if isinstance(jobs, list) else 1
                    summary = f"Started {count} security scan(s)"
                elif 'Collection' in result_data:
                    count = result_data.get('Collection', {}).get('Count', 0)
                    summary = f"Query returned {count} results"
                else:
                    # Generic summary for unknown tool results
                    summary = "Tool execution completed"
                
                return Panel(
                    Text(summary, style=colors['success']),
                    border_style=colors['dim'],
                    padding=(0, 1),
                    title=f"[{colors['dim']}]Tool Result[/{colors['dim']}]",
                    title_align="left"
                )
            else:
                return Text(f"  {content[:200]}...", style=colors['dim'])
        except json.JSONDecodeError:
            return Text(f"  {content[:200]}...", style=colors['dim'])
    
    else:
        # System and other messages
        return Text(f"  {content}", style=colors['dim'])


def summarize_tool_call(tool_data: Dict[str, Any]) -> str:
    """Generate a brief summary of a tool call"""
    tool_name = tool_data.get('name', 'unknown')
    
    if tool_name == 'query':
        # Summarize database queries
        input_data = tool_data.get('input', {})
        node = input_data.get('node', {})
        labels = node.get('labels', [])
        if labels:
            return f"Searched for {', '.join(labels).lower()} entities"
        return "Executed database query"
    
    elif tool_name == 'job':
        # Summarize job execution
        input_data = tool_data.get('input', {})
        target = input_data.get('target', 'unknown target')
        capabilities = input_data.get('capabilities', [])
        if capabilities:
            cap_str = ', '.join(capabilities[:2])
            if len(capabilities) > 2:
                cap_str += f" and {len(capabilities) - 2} more"
            return f"Started {cap_str} scan on {target}"
        return f"Started security scan on {target}"
    
    elif tool_name == 'capabilities':
        return "Listed available security capabilities"
    
    else:
        return f"Executed {tool_name} tool"


def summarize_tool_result(result_data: Dict[str, Any]) -> str:
    """Generate a brief summary of a tool result"""
    if 'capabilities' in result_data:
        count = result_data.get('count', len(result_data.get('capabilities', [])))
        return f"Found {count} available capabilities"
    
    elif 'jobs' in result_data:
        jobs = result_data.get('jobs', [])
        count = len(jobs) if isinstance(jobs, list) else 1
        status = jobs[0].get('status', 'unknown') if jobs else 'unknown'
        return f"Started {count} job(s) with status {status}"
    
    elif 'Collection' in result_data:
        count = result_data.get('Collection', {}).get('Count', 0)
        return f"Found {count} matching records"
    
    elif 'target' in result_data and 'capabilities' in result_data:
        # Job result format
        target = result_data.get('target', 'unknown')
        caps = result_data.get('capabilities', [])
        cap_str = ', '.join(caps[:2])
        if len(caps) > 2:
            cap_str += f" and {len(caps) - 2} more"
        return f"Scan queued: {cap_str} on {target}"
    
    else:
        return "Tool execution completed"