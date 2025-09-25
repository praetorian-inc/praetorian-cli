#!/usr/bin/env python3

import os
import json
import time
import threading
from datetime import datetime
from typing import Optional, List, Dict
from rich.console import Console
from rich.prompt import Prompt, Confirm
from rich.text import Text
from rich.panel import Panel
from rich.markdown import Markdown
from rich.table import Table

from praetorian_cli.sdk.chariot import Chariot


class ConversationMenu:
    """Conversation interface with Chariot AI assistant"""
    
    def __init__(self, sdk: Chariot):
        self.sdk: Chariot = sdk
        self.console = Console()
        self.conversation_id: Optional[str] = None
        self.messages: List[Dict] = []
        self.user_email, self.username = self.sdk.get_current_user()
        self.last_message_key = ""
        self.polling_thread = None
        self.stop_polling = False
        
    def run(self) -> None:
        """Main conversation loop"""
        self.clear_screen()
        
        if not self.choose_conversation_mode():
            return
            
        self.show_header()
        self.start_background_polling()
        
        try:
            while True:
                try:
                    user_input = self.get_user_input()
                    
                    if user_input.lower() in ['quit', 'exit', 'q']:
                        self.console.print("\n[dim]Goodbye![/dim]")
                        break
                    elif user_input.lower() in ['clear', 'cls']:
                        self.clear_screen()
                        self.show_header()
                        continue
                    elif user_input.lower() in ['new']:
                        self.start_new_conversation()
                        continue
                    elif user_input.lower() in ['resume']:
                        self.resume_conversation()
                        continue
                    elif user_input.lower() == 'jobs':
                        self.show_job_status()
                        continue
                    elif user_input.lower() == 'help':
                        self.show_help()
                        continue
                        
                    if user_input.strip():
                        self.send_message_with_polling(user_input)
                        
                except KeyboardInterrupt:
                    self.console.print("\n[dim]Use 'quit' to exit[/dim]")
                    continue
        finally:
            self.stop_background_polling()
    
    def clear_screen(self) -> None:
        """Clear the screen"""
        os.system('clear' if os.name == 'posix' else 'cls')
    
    def show_header(self) -> None:
        """Show conversation header with job status"""
        self.console.print(f"\n[bold blue]Chariot AI Assistant[/bold blue]")
        self.console.print(f"[dim]User: {self.username}[/dim]")
        if self.conversation_id:
            self.console.print(f"[dim]Conversation: {self.conversation_id[:8]}...[/dim]")
            
            # Show job summary in header
            try:
                jobs = self.get_conversation_jobs()
                if jobs:
                    queued_jobs = [j for j in jobs if j.get('status', '').startswith('JQ')]
                    running_jobs = [j for j in jobs if j.get('status', '').startswith('JR')]
                    completed_jobs = [j for j in jobs if j.get('status', '').startswith('JP')]
                    failed_jobs = [j for j in jobs if j.get('status', '').startswith('JF')]
                    
                    status_parts = []
                    if queued_jobs:
                        status_parts.append(f"[blue]{len(queued_jobs)} queued[/blue]")
                    if running_jobs:
                        status_parts.append(f"[yellow]{len(running_jobs)} running[/yellow]")
                    if completed_jobs:
                        status_parts.append(f"[green]{len(completed_jobs)} completed[/green]")
                    if failed_jobs:
                        status_parts.append(f"[red]{len(failed_jobs)} failed[/red]")
                    
                    if status_parts:
                        self.console.print(f"[dim]Jobs: {', '.join(status_parts)}[/dim]")
            except Exception:
                pass
                
        self.console.print()
    
    def choose_conversation_mode(self) -> bool:
        """Choose between new conversation or resume existing"""
        self.console.print(f"\n[bold blue]Chariot AI Assistant[/bold blue]")
        self.console.print(f"[dim]User: {self.username}[/dim]\n")
        
        choice = Prompt.ask("Start [bold green]new[/bold green] conversation or [bold blue]resume[/bold blue] existing?", 
                           choices=["new", "resume", "quit"], default="new")
        
        if choice == "quit":
            return False
        elif choice == "new":
            self.start_new_conversation()
        elif choice == "resume":
            if not self.resume_conversation():
                return False
        
        return True
    
    def resume_conversation(self) -> bool:
        """Resume an existing conversation"""
        try:
            conversations = self.get_recent_conversations()
            if not conversations:
                self.console.print("[yellow]No recent conversations found. Starting new conversation.[/yellow]")
                self.start_new_conversation()
                return True
                
            table = Table(title="Recent Conversations")
            table.add_column("ID", style="cyan", no_wrap=True)
            table.add_column("Topic", style="yellow", max_width=40)
            table.add_column("Created", style="magenta")
            
            for i, conv in enumerate(conversations[:10]):
                topic = conv.get('topic', 'No topic')[:40]
                created = conv.get('created', 'Unknown')[:16]
                table.add_row(str(i + 1), topic, created)
            
            self.console.print(table)
            
            choice = Prompt.ask("\nEnter conversation number (1-10) or 'new' for new conversation", 
                               default="new")
            
            if choice.lower() == 'new':
                self.start_new_conversation()
                return True
            
            try:
                conv_index = int(choice) - 1
                if 0 <= conv_index < len(conversations):
                    self.conversation_id = conversations[conv_index]['uuid']
                    self.console.print(f"[green]Resumed conversation: {self.conversation_id[:8]}...[/green]")
                    self.load_conversation_history()
                    return True
                else:
                    self.console.print("[red]Invalid conversation number[/red]")
                    return False
            except ValueError:
                self.console.print("[red]Invalid input[/red]")
                return False
                
        except Exception as e:
            self.console.print(f"[red]Error loading conversations: {e}[/red]")
            self.start_new_conversation()
            return True

    def get_recent_conversations(self) -> List[Dict]:
        """Get recent conversations for the user"""
        try:
            conversations, _ = self.sdk.search.by_key_prefix("#conversation#", pages=1, user=True)
            return sorted(conversations, key=lambda x: x.get('created', ''), reverse=True)
        except Exception:
            pass
        return []
    

    def show_help(self) -> None:
        """Show help information"""
        help_text = """
**Available Commands:**
- `help` - Show this help
- `clear` - Clear screen
- `new` - Start new conversation
- `resume` - Resume existing conversation
- `jobs` - Show running jobs
- `quit` - Exit

**Query Examples:**
- "Find all active assets"
- "Show me high-priority risks"
- "List assets for example.com"

**Security Scan Examples:**
- "Run a port scan on 10.0.1.5"
- "Check SSL configuration for api.example.com"
- "Scan example.com for subdomains"

The AI can search security data and run scans to discover vulnerabilities.
        """
        self.console.print(Panel(Markdown(help_text), title="Help", border_style="blue"))
        self.console.print()
    
    def start_new_conversation(self) -> None:
        """Start a new conversation"""
        self.conversation_id = None
        self.messages = []
        self.last_message_key = ""
        self.clear_screen()
        self.show_header()
        self.console.print("[green]Started new conversation[/green]\n")
    
    def send_message_with_polling(self, message: str) -> None:
        """Send message and poll for AI response"""
        try:
            with self.console.status(
                "[dim]Thinking...[/dim]",
                spinner="dots",
                spinner_style="blue"
            ) as status:
                response = self.call_conversation_api(message)
                
                if response.get('error'):
                    self.console.print(f"[red]Error: {response.get('error')}[/red]")
                    return
                
                # Wait for AI to respond (background polling handles display)
                while True:
                    if self.conversation_id:
                        # Use efficient greater-than search
                        search_key = f"#message#{self.conversation_id}#{self.last_message_key}" if self.last_message_key else f"#message#{self.conversation_id}#"
                        messages, _ = self.sdk.search.by_term(f"key:>{search_key}", user=True)
                        
                        if messages:
                            messages = sorted(messages, key=lambda x: x.get('key', ''))
                            most_recent = messages[-1]
                            
                            # Update spinner for tool execution
                            for msg in messages:
                                role = msg.get('role')
                                if role == 'tool call':
                                    status.update("[dim]🔧 Executing tool...[/dim]")
                                elif role == 'tool response':
                                    status.update("[dim]✅ Tool completed, thinking...[/dim]")
                            
                            # Stop when AI responds
                            if most_recent.get('role') == 'chariot':
                                break
                    
                    time.sleep(1)
            
        except Exception as e:
            self.console.print(f"[red]Failed to send message: {e}[/red]")
    
    
    def start_background_polling(self):
        """Start continuous background polling for new messages"""
        if self.polling_thread and self.polling_thread.is_alive():
            self.stop_polling = True
            self.polling_thread.join()
        
        self.stop_polling = False
        self.polling_thread = threading.Thread(target=self._background_poll, daemon=True)
        self.polling_thread.start()
    
    def stop_background_polling(self):
        """Stop background polling"""
        self.stop_polling = True
        if self.polling_thread:
            self.polling_thread.join()
    
    def _background_poll(self):
        """Background polling thread - unified message loader"""
        while not self.stop_polling:
            try:
                if self.conversation_id:
                    # Use efficient greater-than search for new messages only
                    search_key = f"#message#{self.conversation_id}#{self.last_message_key}" if self.last_message_key else f"#message#{self.conversation_id}#"
                    messages, _ = self.sdk.search.by_term(f"key:>{search_key}", user=True)
                    
                    if messages:
                        # Sort by key (which includes timestamp ordering)
                        messages = sorted(messages, key=lambda x: x.get('key', ''))
                        
                        for msg in messages:
                            role = msg.get('role')
                            content = msg.get('content', '')
                            
                            if role == 'chariot':
                                # Check if it's a job completion
                                if content.startswith("**Scan Complete**") or content.startswith("**Scan Failed**"):
                                    self.console.print(f"\n[bold green]🎯 Job Update:[/bold green]")
                                    self.display_ai_response(content)
                                else:
                                    self.display_ai_response(content)
                            elif role == 'tool call':
                                self.console.print(f"[dim]🔧 Executing tool...[/dim]")
                            elif role == 'tool response':
                                self.console.print(f"[dim]✅ Tool execution completed[/dim]")
                            elif role == 'planner-output':
                                self.console.print(f"[dim]🎯 Processing job completion...[/dim]")
                        
                        # Update last message key for next poll
                        self.last_message_key = messages[-1].get('key', '')
                
                time.sleep(2)
            except Exception:
                pass
    
    
    def get_user_input(self) -> str:
        """Get user input with prompt"""
        try:
            return Prompt.ask("[bold green]You[/bold green]", default="")
        except (EOFError, KeyboardInterrupt):
            return "quit"
    
    
    def call_conversation_api(self, message: str) -> Dict:
        """Call the Chariot conversation API"""
        url = self.sdk.url("/planner")
        payload = {"message": message}
        
        if self.conversation_id:
            payload["conversationId"] = self.conversation_id
        
        response = self.sdk._make_request("POST", url, json=payload)
        
        if response.status_code == 200:
            result = response.json()
            
            if not self.conversation_id and 'conversation' in result:
                self.conversation_id = result['conversation'].get('uuid')
            
            return {'success': True}
        else:
            return {
                'success': False,
                'error': f"API error: {response.status_code} - {response.text}"
            }
    
    def display_ai_response(self, response: str) -> None:
        """Display AI response with proper formatting"""
        self.console.print()
        
        # Check for job completion (🎯 prefix indicates results)
        if response.startswith("🎯"):
            self.console.print(Panel(
                response,
                title="[bold green]Security Scan Results[/bold green]",
                border_style="green"
            ))
            self.console.print()
            return
            
        if response.startswith("**Scan Complete**") or response.startswith("**Scan Failed**"):
            border_style = "green" if "Complete" in response else "red"
            title_style = "[bold green]Scan Complete[/bold green]" if "Complete" in response else "[bold red]Scan Failed[/bold red]"
            self.console.print(Panel(
                response,
                title=title_style,
                border_style=border_style
            ))
            self.console.print()
            return
        
        # Check if response contains formatted query results
        if "```json" in response:
            # Split response into text and JSON parts
            parts = response.split("```json")
            if len(parts) > 1:
                text_part = parts[0].strip()
                json_parts = parts[1].split("```")
                if len(json_parts) > 1:
                    json_part = json_parts[0].strip()
                    remaining_text = "```".join(json_parts[1:]).strip()
                    
                    # Display text part
                    if text_part:
                        self.console.print(Panel(
                            text_part,
                            title="[bold blue]Chariot AI[/bold blue]",
                            border_style="blue"
                        ))
                    
                    # Display truncated JSON (first 5 lines for preview)
                    json_lines = json_part.split('\n')
                    if len(json_lines) > 5:
                        preview_lines = json_lines[:5]
                        truncated_json = '\n'.join(preview_lines) + f"\n... [{len(json_lines)-5} more lines truncated]"
                        title = f"Tool Output Preview (showing 5/{len(json_lines)} lines)"
                        border_color = "yellow"
                    else:
                        truncated_json = json_part
                        title = "Tool Output"
                        border_color = "green"
                    
                    try:
                        # Try to format as valid JSON for short content
                        if len(json_lines) <= 5:
                            parsed_json = json.loads(json_part)
                            formatted_json = json.dumps(parsed_json, indent=2)
                            self.console.print(Panel(
                                formatted_json,
                                title=title,
                                border_style=border_color
                            ))
                        else:
                            # Show raw preview for truncated content
                            self.console.print(Panel(
                                truncated_json,
                                title=title,
                                border_style=border_color
                            ))
                    except json.JSONDecodeError:
                        self.console.print(Panel(
                            truncated_json,
                            title="Raw Tool Output Preview",
                            border_style="yellow"
                        ))
                    
                    # Display any remaining text
                    if remaining_text:
                        self.console.print(remaining_text)
                else:
                    # Fallback to simple display
                    self.console.print(Panel(
                        response,
                        title="[bold blue]Chariot AI[/bold blue]",
                        border_style="blue"
                    ))
            else:
                # No JSON formatting needed
                self.console.print(Panel(
                    response,
                    title="[bold blue]Chariot AI[/bold blue]",
                    border_style="blue"
                ))
        else:
            # Simple text response
            self.console.print(Panel(
                response,
                title="[bold blue]Chariot AI[/bold blue]",
                border_style="blue"
            ))
        
        self.console.print()

    def show_job_status(self) -> None:
        """Show active jobs for the current conversation"""
        if not self.conversation_id:
            self.console.print("[dim]No active conversation[/dim]")
            return
            
        try:
            conversation_jobs = self.get_conversation_jobs()
            
            if not conversation_jobs:
                self.console.print("[dim]No jobs found for this conversation[/dim]")
                return
            
            self.console.print(f"[bold]Jobs for this conversation: {len(conversation_jobs)}[/bold]\n")
            
            for job in conversation_jobs:
                status_color = self.get_job_status_color(job.get('status', ''))
                status_text = self.get_job_status_text(job.get('status', ''))
                
                # Extract target from job key format: #job#target#capability
                job_key = job.get('key', '')
                if job_key.startswith('#job#'):
                    parts = job_key.split('#')
                    if len(parts) >= 3:
                        target_part = parts[2]  # target part from job key
                        # If target is an asset key, extract readable name
                        if target_part.startswith('#asset#'):
                            asset_parts = target_part.split('#')
                            if len(asset_parts) >= 4:
                                target_display = asset_parts[3]  # hostname/ip from asset key
                            else:
                                target_display = target_part
                        else:
                            target_display = target_part
                    else:
                        target_display = job_key
                else:
                    target_display = job.get('dns', 'unknown')
                
                capability = job.get('source', 'unknown')
                self.console.print(f"[{status_color}]• {capability}[/{status_color}] on {target_display} - {status_text}")
                
        except Exception as e:
            self.console.print(f"[red]Failed to get job status: {e}[/red]")

    def get_conversation_jobs(self) -> list:
        """Get jobs for the current conversation using conversation:<uuid> pattern"""
        try:
            jobs, _ = self.sdk.search.by_term(f"conversation:{self.conversation_id}")
            return jobs if jobs else []
        except Exception:
            return []

    def get_job_status_color(self, status: str) -> str:
        """Get color for job status display"""
        if status.startswith("JP"):
            return "green"
        elif status.startswith("JR"):
            return "yellow"
        elif status.startswith("JQ"):
            return "blue"
        elif status.startswith("JF"):
            return "red"
        else:
            return "white"
    
    def get_job_status_text(self, status: str) -> str:
        """Map job status codes to human-readable text"""
        if status.startswith("JQ"):
            return "Queued"
        elif status.startswith("JR"):
            return "Running"
        elif status.startswith("JP"):
            return "Completed"
        elif status.startswith("JF"):
            return "Failed"
        else:
            return status
    
    def load_conversation_history(self) -> None:
        """Load and display previous messages when resuming conversation"""
        try:
            if not self.conversation_id:
                return
                
            # Use greater-than search for efficient loading
            messages, _ = self.sdk.search.by_term(f"key:>#message#{self.conversation_id}#", user=True)
            messages = sorted(messages, key=lambda x: x.get('key', ''))
            
            self.console.print(f"\n[dim]Loading conversation history ({len(messages)} messages)...[/dim]\n")
            
            for msg in messages:
                role = msg.get('role')
                content = msg.get('content', '')
                
                if role == 'user':
                    self.console.print(f"[bold blue]You:[/bold blue] {content}")
                elif role == 'chariot':
                    self.console.print(f"[bold green]AI:[/bold green]")
                    self.display_ai_response(content)
                elif role == 'tool call':
                    self.console.print("[dim]🔧 Executing tool...[/dim]")
                elif role == 'tool response':
                    self.console.print("[dim]✅ Tool execution completed[/dim]")
                elif role == 'planner-output':
                    self.console.print("[dim]🎯 Job completion summary[/dim]")
            
            # Set last message key for background polling
            if messages:
                self.last_message_key = messages[-1].get('key', '')
            
            self.console.print()
            
        except Exception as e:
            self.console.print(f"[red]Error loading conversation history: {e}[/red]")


def run_conversation_menu(sdk: Chariot) -> None:
    """Run the conversation menu interface"""
    menu = ConversationMenu(sdk)
    menu.run()