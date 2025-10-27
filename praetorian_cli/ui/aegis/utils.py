#!/usr/bin/env python3
"""
Aegis UI Utility Functions
Helper functions for formatting, time calculations, and other utilities
"""

from datetime import datetime
from typing import Optional, List
from praetorian_cli.sdk.model.aegis import Agent
from rich.text import Text


def relative_time(ts_seconds: float, now_seconds: float) -> str:
    """Render clean, minimal relative time"""
    delta = max(0, int(now_seconds - ts_seconds))
    if delta < 5:
        return "just now"
    if delta < 60:
        return f"{delta}s"
    minutes = delta // 60
    if minutes < 60:
        return f"{minutes}m"
    hours = minutes // 60
    if hours < 24:
        return f"{hours}h"
    if hours < 48:
        return "yesterday"
    days = hours // 24
    if days < 7:
        return f"{days}d"
    weeks = days // 7
    if weeks < 4:
        return f"{weeks}w"
    return "long ago"



def format_job_status(status: str, colors: dict) -> Text:
    """Format job status for display with appropriate color"""
    status_upper = status.upper()
    
    if status_upper.startswith('JP'):  # Job Passed
        return Text("PASSED", style=f"{colors['success']}")
    elif status_upper.startswith('JF'):  # Job Failed
        return Text("FAILED", style=f"{colors['error']}")
    elif status_upper.startswith('JR'):  # Job Running
        return Text("RUNNING", style=f"{colors['warning']}")
    elif status_upper.startswith('JQ'):  # Job Queued
        return Text("QUEUED", style=f"{colors['info']}")
    else:
        return Text(status[:8].upper(), style=f"{colors['dim']}")


def format_os_display(os_info: str, os_version: str = "", max_length: int = 18) -> str:
    """Format OS information for table display"""
    if not os_info:
        return "unknown"
    
    os_full = os_info.lower()
    version = os_version or ""
    display = f"{os_full} {version}".strip()
    
    return display[:max_length] if len(display) > max_length else display




def format_timestamp(timestamp: float, format_str: str = "%m/%d %H:%M") -> str:
    """Format timestamp for display"""
    if not timestamp:
        return "—"
    
    try:
        dt = datetime.fromtimestamp(timestamp)
        return dt.strftime(format_str)
    except (ValueError, OSError):
        return "—"


def compute_agent_groups(agents: List[Agent], current_time: float) -> dict:
    """Compute agent status groups for display organization"""
    groups = {
        'active_tunnel': [],
        'online': [],
        'offline': []
    }
    
    for i, agent in enumerate(agents):
        # Compute relative time string
        if agent.last_seen_at > 0 and agent.is_online:
            last_seen_str = relative_time(agent.last_seen_at / 1000000 if agent.last_seen_at > 1000000000000 else agent.last_seen_at, current_time)
        else:
            last_seen_str = "—"
        
        # Determine group
        if agent.is_online and getattr(agent, 'has_tunnel', False):
            group = 'active_tunnel'
        elif agent.is_online:
            group = 'online'
        else:
            group = 'offline'
        
        # Store agent with computed data
        agent_data = (i + 1, agent)  # Store 1-based index with agent
        groups[group].append(agent_data)
    
    return groups


def get_agent_display_style(group: str, colors: dict) -> dict:
    """Get display styles for agent based on group"""
    if group == 'active_tunnel':
        return {
            'status': Text("online", style=f"{colors['success']}"),
            'tunnel': Text("active", style=f"{colors['warning']}"),
            'idx_style': f"{colors['warning']}",
            'hostname_style': "bold white"
        }
    elif group == 'online':
        return {
            'status': Text("online", style=f"{colors['success']}"),
            'tunnel': Text("—", style=f"{colors['dim']}"),
            'idx_style': f"{colors['success']}",
            'hostname_style': "white"
        }
    else:  # offline
        return {
            'status': Text("offline", style=f"{colors['dim']}"),
            'tunnel': Text("—", style=f"{colors['dim']}"),
            'idx_style': f"{colors['dim']}",
            'hostname_style': f"{colors['dim']}"
        }


def parse_agent_identifier(identifier: str, displayed_agents: List[Agent], all_agents: Optional[List[Agent]] = None) -> Optional[Agent]:
    """Parse agent identifier and return matching agent
    """
    if not displayed_agents:
        return None
    
    # Use all_agents for fallback searches, or displayed_agents if not provided
    search_agents = all_agents if all_agents is not None else displayed_agents
    
    if identifier.isdigit():
        agent_num = int(identifier)
        if 1 <= agent_num <= len(displayed_agents):
            return displayed_agents[agent_num - 1]
    
    for agent in search_agents:
        try:
            if agent.client_id and agent.client_id.lower() == identifier.lower():
                return agent
        except AttributeError:
            continue
    
    for agent in search_agents:
        try:
            if agent.hostname and agent.hostname.lower() == identifier.lower():
                return agent
        except AttributeError:
            continue
    
    return None