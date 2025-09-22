#!/usr/bin/env python3

import os
import json
import uuid
from datetime import datetime
from typing import Optional, List, Dict
from rich.console import Console
from rich.prompt import Prompt
from rich.text import Text
from rich.panel import Panel
from rich.markdown import Markdown

from praetorian_cli.sdk.chariot import Chariot


class ConversationMenu:
    """Conversation interface with Chariot AI assistant"""
    
    def __init__(self, sdk: Chariot):
        self.sdk: Chariot = sdk
        self.console = Console()
        self.conversation_id: Optional[str] = None
        self.messages: List[Dict] = []
        self.user_email, self.username = self.sdk.get_current_user()
        
    def run(self) -> None:
        """Main conversation loop"""
        self.clear_screen()
        self.show_header()
        self.start_conversation()
        
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
                elif user_input.lower() in ['new', 'restart']:
                    self.start_new_conversation()
                    continue
                elif user_input.lower() == 'help':
                    self.show_help()
                    continue
                    
                if user_input.strip():
                    self.send_message(user_input)
                    
            except KeyboardInterrupt:
                self.console.print("\n[dim]Use 'quit' to exit[/dim]")
                continue
    
    def clear_screen(self) -> None:
        """Clear the screen"""
        os.system('clear' if os.name == 'posix' else 'cls')
    
    def show_header(self) -> None:
        """Show conversation header"""
        self.console.print(f"\n[bold blue]Chariot AI Assistant[/bold blue]")
        self.console.print(f"[dim]User: {self.username}[/dim]")
        if self.conversation_id:
            self.console.print(f"[dim]Conversation: {self.conversation_id[:8]}...[/dim]")
        self.console.print()
    
    def show_help(self) -> None:
        """Show help information"""
        help_text = """
**Available Commands:**
- `help` - Show this help
- `clear` - Clear screen
- `new` - Start new conversation  
- `quit` - Exit

**Query Examples:**
- "Find all active assets"
- "Show me high-priority risks"
- "List assets for example.com"
- "What vulnerabilities do we have?"

**Security Scan Examples:**
- "Scan webapp.example.com for vulnerabilities"
- "Run a port scan on 10.0.1.5"
- "Check SSL configuration for api.example.com"
- "Scan example.com for subdomains"

**Available Security Capabilities:**
- **nuclei**: Web application vulnerability scanning
- **nmap**: Network port scanning
- **ssl-analyzer**: SSL/TLS analysis
- **aws-security-scan**: Cloud security assessment

The AI can both search existing security data and run new scans to discover vulnerabilities.
        """
        self.console.print(Panel(Markdown(help_text), title="Help", border_style="blue"))
        self.console.print()
    
    def start_conversation(self) -> None:
        """Start a new conversation"""
        if not self.conversation_id:
            self.conversation_id = str(uuid.uuid4())
            self.messages = []
            if os.getenv('CHARIOT_CLI_VERBOSE'):
                self.console.print(f"[dim]Started new conversation: {self.conversation_id}[/dim]")
    
    def start_new_conversation(self) -> None:
        """Reset and start a new conversation"""
        self.conversation_id = str(uuid.uuid4())
        self.messages = []
        self.clear_screen()
        self.show_header()
        self.console.print("[green]Started new conversation[/green]\n")
    
    def get_user_input(self) -> str:
        """Get user input with prompt"""
        try:
            return Prompt.ask("[bold green]You[/bold green]", default="")
        except (EOFError, KeyboardInterrupt):
            return "quit"
    
    def send_message(self, message: str) -> None:
        """Send message to AI and display response"""
        try:
            with self.console.status(
                "[dim]Thinking...[/dim]",
                spinner="dots",
                spinner_style="blue"
            ):
                response = self.call_conversation_api(message)
            
            if response.get('success'):
                ai_response = response.get('response', 'No response received')
                self.display_ai_response(ai_response)
                self.messages.append({
                    'user': message,
                    'ai': ai_response,
                    'timestamp': datetime.now().isoformat()
                })
            else:
                self.console.print(f"[red]Error: {response.get('error', 'Unknown error')}[/red]")
                
        except Exception as e:
            self.console.print(f"[red]Failed to send message: {e}[/red]")
    
    def call_conversation_api(self, message: str) -> Dict:
        """Call the Chariot conversation API"""
        url = self.sdk.url("/planner")
        payload = {
            "conversationId": self.conversation_id,
            "message": message
        }
        
        response = self.sdk._make_request("POST", url, json=payload)
        
        if response.status_code == 200:
            return response.json().get('response', {})
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


def run_conversation_menu(sdk: Chariot) -> None:
    """Run the conversation menu interface"""
    menu = ConversationMenu(sdk)
    menu.run()