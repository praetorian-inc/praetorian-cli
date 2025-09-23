#!/usr/bin/env python3
"""
Conversation Menu Interface - AI Planner Chat Interface
Interactive conversation interface for Chariot's AI planner system
"""

import os
import json
import uuid
from datetime import datetime
from typing import List, Optional, Dict, Any
from rich.console import Console
from rich.prompt import Prompt, Confirm
from rich.table import Table
from rich.text import Text
from rich.box import MINIMAL
from rich.markdown import Markdown
from rich.panel import Panel

from praetorian_cli.sdk.chariot import Chariot
from .constants import DEFAULT_COLORS
from .utils import format_timestamp, format_message_role, parse_message_content


class ConversationMenu:
    """Conversation menu interface for AI planner interactions"""
    
    def __init__(self, sdk: Chariot):
        self.sdk: Chariot = sdk
        self.console = Console()
        self.conversations: List[Dict[str, Any]] = []
        self.current_conversation_id: Optional[str] = None
        self.current_messages: List[Dict[str, Any]] = []
        self.colors = DEFAULT_COLORS
        self._first_render = True
        
        self.user_email, self.username = self.sdk.get_current_user()
        
        # Command registry
        self.commands = {
            'help': self._handle_help,
            'h': self._handle_help,
            '?': self._handle_help,
            'list': self._handle_list_conversations,
            'ls': self._handle_list_conversations,
            'new': self._handle_new_conversation,
            'n': self._handle_new_conversation,
            'select': self._handle_select_conversation,
            'sel': self._handle_select_conversation,
            's': self._handle_select_conversation,
            'resume': self._handle_select_conversation,
            'r': self._handle_select_conversation,
            'history': self._handle_show_history,
            'hist': self._handle_show_history,
            'clear': self._handle_clear_screen,
            'cls': self._handle_clear_screen,
            'exit': self._handle_exit,
            'quit': self._handle_exit,
            'q': self._handle_exit,
        }

    def run(self):
        """Main conversation interface loop"""
        try:
            self._show_welcome()
            self._load_conversations()
            
            while True:
                try:
                    # Show status line
                    self._show_status()
                    
                    # Get user input
                    user_input = Prompt.ask(self._get_prompt()).strip()
                    
                    if not user_input:
                        continue
                        
                    # Check if it's a command
                    if user_input.startswith('/') or user_input.lower() in self.commands:
                        self._handle_command(user_input)
                    else:
                        # Send as message to current conversation
                        self._handle_message(user_input)
                        
                except KeyboardInterrupt:
                    if Confirm.ask("\n  Exit conversation interface?"):
                        break
                    self.console.print()
                except EOFError:
                    break
                    
        except Exception as e:
            self.console.print(f"[red]Error in conversation interface: {e}[/red]")
            
    def _show_welcome(self):
        """Show welcome message"""
        self.console.clear()
        welcome_text = """
# Chariot AI Security Assistant

Welcome to the Chariot AI planner interface! You can:
- Chat naturally with the AI about security questions
- Ask it to run scans and analyze results  
- Query your attack surface data
- Get intelligent security recommendations

Type `/help` for commands or just start typing to chat.
        """
        
        panel = Panel(
            Markdown(welcome_text),
            title="[bold cyan]AI Security Assistant[/bold cyan]",
            border_style="cyan",
            padding=(1, 2)
        )
        self.console.print(panel)
        self.console.print()

    def _show_status(self):
        """Show current conversation status"""
        if self.current_conversation_id:
            conv_display = self.current_conversation_id[:8] + "..."
            message_count = len(self.current_messages)
            status = f"[{self.colors['dim']}]Conversation: {conv_display} ({message_count} messages)[/{self.colors['dim']}]"
        else:
            status = f"[{self.colors['dim']}]No active conversation - type /new to start[/{self.colors['dim']}]"
            
        self.console.print(status)

    def _get_prompt(self):
        """Get the input prompt"""
        if self.current_conversation_id:
            return f"[{self.colors['primary']}]Chat[/{self.colors['primary']}]> "
        else:
            return f"[{self.colors['dim']}]Command[/{self.colors['dim']}]> "

    def _load_conversations(self):
        """Load user's conversations"""
        try:
            conversations, _ = self.sdk.conversations.list_conversations()
            self.conversations = conversations or []
            
            if self.conversations and not self.current_conversation_id:
                # Auto-select most recent conversation
                latest = max(self.conversations, key=lambda x: x.get('created', ''))
                self.current_conversation_id = latest.get('uuid')
                self._load_conversation_messages()
                
        except Exception as e:
            self.console.print(f"[yellow]Warning: Could not load conversations: {e}[/yellow]")
            self.conversations = []

    def _load_conversation_messages(self):
        """Load messages for current conversation"""
        if not self.current_conversation_id:
            self.current_messages = []
            return
            
        try:
            messages, _ = self.sdk.conversations.list_messages(self.current_conversation_id)
            self.current_messages = messages or []
            
            # Sort by timestamp to ensure proper ordering
            self.current_messages.sort(key=lambda x: x.get('timestamp', ''))
            
        except Exception as e:
            self.console.print(f"[yellow]Warning: Could not load messages: {e}[/yellow]")
            self.current_messages = []

    def _handle_command(self, user_input: str):
        """Handle command input"""
        if user_input.startswith('/'):
            cmd = user_input[1:].split()[0].lower()
            args = user_input[1:].split()[1:] if len(user_input[1:].split()) > 1 else []
        else:
            cmd = user_input.lower()
            args = []
            
        if cmd in self.commands:
            self.commands[cmd](args)
        else:
            self.console.print(f"[red]Unknown command: {cmd}[/red]")
            self.console.print("Type [cyan]/help[/cyan] for available commands")

    def _handle_message(self, message: str):
        """Handle sending a message to the AI"""
        if not self.current_conversation_id:
            self.console.print("[yellow]No active conversation. Use [cyan]/new[/cyan] to start one.[/yellow]")
            return
            
        try:
            # Show thinking indicator
            with self.console.status(f"[{self.colors['dim']}]AI is thinking...[/{self.colors['dim']}]"):
                response = self.sdk.conversations.send_message(self.current_conversation_id, message)
            
            # Reload messages to get the complete conversation
            self._load_conversation_messages()
            
            # Display the new messages
            self._show_recent_messages(num_messages=2)  # Show user message + AI response
            
        except Exception as e:
            self.console.print(f"[red]Error sending message: {e}[/red]")

    def _show_recent_messages(self, num_messages: int = 5):
        """Show recent messages in the conversation"""
        if not self.current_messages:
            return
            
        recent = self.current_messages[-num_messages:]
        self.console.print()
        
        for msg in recent:
            self._display_message(msg)
        
        self.console.print()

    def _display_message(self, message: Dict[str, Any]):
        """Display a single message with proper formatting"""
        role = message.get('role', 'unknown')
        content = message.get('content', '')
        timestamp = message.get('timestamp', '')
        username = message.get('username', '')
        
        # Format the role and metadata
        role_display = format_message_role(role, self.colors)
        time_display = format_timestamp(timestamp) if timestamp else ''
        
        # Parse and format the content based on message type
        formatted_content = parse_message_content(role, content, self.colors)
        
        # Create header
        if role == 'user':
            header = f"{role_display} [{self.colors['dim']}]{time_display}[/{self.colors['dim']}]"
        elif role == 'chariot':
            header = f"{role_display} [{self.colors['dim']}]{time_display}[/{self.colors['dim']}]"
        elif role in ['tool call', 'tool response']:
            header = f"{role_display} [{self.colors['dim']}]{time_display}[/{self.colors['dim']}]"
        else:
            header = f"{role_display} [{self.colors['dim']}]{time_display}[/{self.colors['dim']}]"
        
        self.console.print(header)
        self.console.print(formatted_content)
        self.console.print()

    # Command handlers
    def _handle_help(self, args: List[str]):
        """Show help information"""
        help_text = """
[bold cyan]Conversation Commands:[/bold cyan]

[bold]Navigation:[/bold]
  /help, /h, /?          Show this help
  /list, /ls             List all conversations  
  /new, /n               Start a new conversation
  /select <id>, /s <id>  Select a conversation by ID
  /resume <id>, /r <id>  Resume a conversation (alias for select)
  
[bold]Messages:[/bold]
  /history, /hist        Show conversation history
  /clear, /cls           Clear screen
  
[bold]Other:[/bold]
  /exit, /quit, /q       Exit conversation interface

[bold]Chat Usage:[/bold]
Just type naturally to chat with the AI! Examples:
- "Show me all critical vulnerabilities on example.com"
- "Run a port scan on 10.0.1.5" 
- "What are my riskiest assets?"
- "Help me understand this CVE-2024-12345"

The AI can query your data and run security scans to help answer questions.
        """
        self.console.print(Markdown(help_text))

    def _handle_list_conversations(self, args: List[str]):
        """List all conversations"""
        if not self.conversations:
            self.console.print("[yellow]No conversations found. Use [cyan]/new[/cyan] to start one.[/yellow]")
            return
            
        # Create table
        table = Table(
            show_header=True,
            header_style=f"bold {self.colors['primary']}",
            border_style=self.colors['dim'],
            box=MINIMAL,
            show_lines=False,
            padding=(0, 2),
            pad_edge=False
        )
        
        table.add_column("ID", style=f"bold {self.colors['accent']}", width=12, no_wrap=True)
        table.add_column("CREATED", style=f"{self.colors['dim']}", width=12, justify="right", no_wrap=True)
        table.add_column("STATUS", width=8, justify="center", no_wrap=True)
        
        self.console.print()
        self.console.print("  Your Conversations")
        self.console.print()
        
        # Sort by creation date (most recent first)
        sorted_conversations = sorted(
            self.conversations, 
            key=lambda x: x.get('created', ''), 
            reverse=True
        )
        
        for conv in sorted_conversations[:20]:  # Show most recent 20
            conv_id = conv.get('uuid', '')[:8] + "..."
            created = format_timestamp(conv.get('created', ''))
            
            # Mark current conversation
            status = "ACTIVE" if conv.get('uuid') == self.current_conversation_id else ""
            status_style = f"[{self.colors['success']}]ACTIVE[/{self.colors['success']}]" if status else ""
            
            table.add_row(conv_id, created, status_style)
        
        self.console.print(table)
        self.console.print()

    def _handle_new_conversation(self, args: List[str]):
        """Start a new conversation"""
        try:
            with self.console.status("[dim]Creating new conversation...[/dim]"):
                result = self.sdk.conversations.create_conversation()
                
            self.current_conversation_id = result['uuid']
            self.current_messages = []
            
            # Reload conversations list
            self._load_conversations()
            
            conv_display = self.current_conversation_id[:8] + "..."
            self.console.print(f"[{self.colors['success']}]✓ Started new conversation {conv_display}[/{self.colors['success']}]")
            self.console.print("You can now start chatting with the AI!")
            
        except Exception as e:
            self.console.print(f"[red]Error creating conversation: {e}[/red]")

    def _handle_select_conversation(self, args: List[str]):
        """Select/resume a conversation"""
        if not args:
            self.console.print("[yellow]Usage: /select <conversation_id>[/yellow]")
            self.console.print("Use [cyan]/list[/cyan] to see available conversations")
            return
            
        target_id_prefix = args[0].lower()
        
        # Find matching conversation
        matches = []
        for conv in self.conversations:
            conv_id = conv.get('uuid', '')
            if conv_id.lower().startswith(target_id_prefix) or target_id_prefix in conv_id.lower():
                matches.append(conv)
        
        if not matches:
            self.console.print(f"[red]No conversation found matching '{target_id_prefix}'[/red]")
            return
        elif len(matches) > 1:
            self.console.print(f"[yellow]Multiple matches found for '{target_id_prefix}'. Please be more specific.[/yellow]")
            for match in matches[:5]:
                conv_display = match.get('uuid', '')[:12] + "..."
                created = format_timestamp(match.get('created', ''))
                self.console.print(f"  {conv_display} (created {created})")
            return
        
        # Select the conversation
        selected = matches[0]
        self.current_conversation_id = selected.get('uuid')
        
        # Load messages
        self._load_conversation_messages()
        
        conv_display = self.current_conversation_id[:8] + "..."
        message_count = len(self.current_messages)
        self.console.print(f"[{self.colors['success']}]✓ Selected conversation {conv_display} ({message_count} messages)[/{self.colors['success']}]")
        
        # Show recent messages
        if self.current_messages:
            self.console.print("\nRecent messages:")
            self._show_recent_messages(num_messages=3)

    def _handle_show_history(self, args: List[str]):
        """Show conversation history"""
        if not self.current_conversation_id:
            self.console.print("[yellow]No active conversation selected[/yellow]")
            return
            
        if not self.current_messages:
            self.console.print("[yellow]No messages in this conversation yet[/yellow]")
            return
        
        self.console.print(f"\n[bold]Conversation History[/bold] ({len(self.current_messages)} messages)")
        self.console.print("─" * 60)
        
        for msg in self.current_messages:
            self._display_message(msg)

    def _handle_clear_screen(self, args: List[str]):
        """Clear the screen"""
        self.console.clear()

    def _handle_exit(self, args: List[str]):
        """Exit the conversation interface"""
        self.console.print("Goodbye!")
        exit(0)