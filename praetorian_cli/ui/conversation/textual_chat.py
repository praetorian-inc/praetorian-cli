#!/usr/bin/env python3

import asyncio
import json
import time
from datetime import datetime
from typing import Dict, Optional

from rich.markup import escape
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Container, VerticalScroll
from textual.widgets import Header, Footer, Input, Static, Markdown
from textual.reactive import reactive
from textual import on

from praetorian_cli.sdk.chariot import Chariot
from praetorian_cli.ui.conversation.approvals import (
    APPROVAL_POLL_INTERVAL_SECONDS,
    ApprovalContextError,
    credential_field_is_optional,
    format_endpoint_approval,
    normalize_credential_interaction_fields,
    parse_endpoint_approval,
    submit_ephemeral_credentials,
)
from praetorian_cli.ui.conversation.endpoint_status import (
    ENDPOINT_STATUS_POLL_INTERVAL_SECONDS,
    endpoint_status_fingerprint,
    format_endpoint_execution_status,
)


class ConversationApp(App):
    """Textual-based conversation interface with separate chat log and input"""
    
    CSS = """
    Screen {
        layout: vertical;
        background: #0d0d28;
    }
    
    #chat-container {
        height: 1fr;
        border: solid #323452;
        margin: 1;
        background: #0d0d28;
    }
    
    #input-container {
        height: 7;
        border: solid #5f47b7;
        margin: 0 1 0 1;
        background: #28205a;
    }
    
    .user-message {
        background: #28205a;
        color: #afa3db;
        padding: 1;
        margin: 0 0 1 0;
        border-left: thick #5f47b7;
    }
    
    .ai-message {
        background: #3d3d53;
        color: #ece6fc;
        padding: 1;
        margin: 0 0 1 0;
        border-left: thick #5f47b7;
    }
    
    .tool-message {
        color: #afa3db;
        padding: 0 1;
        text-style: italic;
        background: #323452;
    }
    
    .system-message {
        color: #ece6fc;
        padding: 0 1;
        text-style: italic;
        background: #25253e;
    }
    
    Input {
        height: 3;
        margin: 1 1;
        background: #0d0d28;
        color: #ece6fc;
        border: solid #323452;
    }
    
    #status-bar {
        height: 1;
        background: #323452;
        color: #afa3db;
        padding: 0 1;
    }
    
    Header {
        background: #0d0d28;
        color: #ece6fc;
    }
    
    Footer {
        background: #323452;
        color: #afa3db;
    }
    """
    
    TITLE = "Guard AI Assistant"
    BINDINGS = [
        Binding("ctrl+x", "stop_agent", "Stop agent", priority=True),
        Binding("escape", "go_back", "Back", priority=True),
        Binding("ctrl+c", "go_back", "Back", show=False, priority=True),
    ]
    
    # Reactive attributes
    conversation_id: reactive[Optional[str]] = reactive(None)
    last_message_key: reactive[str] = reactive("")
    mode: reactive[str] = reactive("query")
    
    def __init__(self, sdk: Chariot, mode: str = "query"):
        super().__init__()
        self.sdk = sdk
        self.mode = mode
        self.root_conversation_id = None
        self.user_email, self.username = self.sdk.get_current_user()
        self.polling_task: Optional[asyncio.Task] = None
        self._selecting_conversation = False
        self._available_conversations = []
        self._pending_approval = None
        self._pending_approval_context = None
        self._pending_credential = None
        self._credential_fields = ()
        self._credential_field_index = 0
        self._credential_values = {}
        self._shown_interaction_ids = set()
        self._interaction_lock = asyncio.Lock()
        self._message_poll_lock = asyncio.Lock()
        self._next_interaction_poll = 0
        self._next_endpoint_status_poll = 0
        self._last_endpoint_status = None
        
    def compose(self) -> ComposeResult:
        """Compose the UI layout"""
        yield Header()
        
        # Main chat area with scrolling
        with Container(id="chat-container"):
            yield VerticalScroll(id="chat-log")
        
        # Status bar showing conversation info
        yield Static(f"User: {self.username} | Mode: {self.mode} | Ready", id="status-bar")
        
        # Input area at bottom
        with Container(id="input-container"):
            yield Input(placeholder="Type your message here... (type 'help' for commands)", id="message-input")
        
        yield Footer()
    
    def on_mount(self) -> None:
        """Called when app starts"""
        # Start background polling for job completion events
        self.polling_task = asyncio.create_task(self.background_poll())
        
        # Focus the input
        self.query_one("#message-input").focus()
        
        # Show welcome message
        self.add_system_message("Welcome to Guard AI Assistant! Type 'help' for commands or ask about your security data.")

    def on_unmount(self) -> None:
        if self.polling_task:
            self.polling_task.cancel()
        self._credential_values.clear()
    
    @on(Input.Submitted, "#message-input")
    async def on_input_submitted(self, event: Input.Submitted) -> None:
        """Handle user input, including masked interaction responses."""
        raw_value = event.value
        input_widget = self.query_one("#message-input")
        input_widget.clear()

        if self._pending_credential:
            await self.answer_pending_credential(raw_value)
            return

        message = raw_value.strip()
        if not message:
            return

        if message.lower() in ['quit', 'exit', 'q']:
            self.exit()
            return
        if message.lower() == '/agents':
            await self.show_agent_tree()
            return
        if message.lower().startswith('/focus '):
            await self.focus_agent(message)
            return
        if message.lower().startswith('/guide '):
            await self.guide_agent(message)
            return
        if (
            message.lower() in ('stop', '/stop')
            or message.lower().startswith('/stop ')
        ):
            parts = message.split(maxsplit=1)
            await self.stop_current_agent(
                parts[1] if len(parts) == 2 else None
            )
            return
        if self._pending_approval:
            await self.answer_pending_approval(message)
            return
        if message.lower() in ['clear', 'cls']:
            await self.clear_chat()
            return
        if message.lower() == 'help':
            self.show_help()
            return
        if message.lower() in ['new']:
            await self.start_new_conversation()
            return
        if message.lower() in ['resume']:
            await self.resume_conversation()
            return
        if message.lower() in ['mode query', 'query']:
            self.set_mode('query')
            return
        if message.lower() in ['mode agent', 'agent']:
            self.set_mode('agent')
            return
        if message.lower() == 'jobs':
            await self.show_job_status()
            return

        if self._selecting_conversation:
            await self.handle_conversation_selection(message)
            return

        await self.send_message(message)

    async def action_stop_agent(self) -> None:
        """Stop Marcus and correlated child work from the footer shortcut."""
        await self.stop_current_agent()

    def action_go_back(self) -> None:
        self.exit(result='back')

    async def stop_current_agent(self, target_ref=None) -> None:
        try:
            conversation_id = await self._resolve_agent_reference(target_ref)
        except ValueError as exc:
            self.add_system_message(escape(str(exc)))
            return
        try:
            await asyncio.to_thread(
                self.sdk.conversations.stop,
                conversation_id,
            )
        except Exception:
            self.add_system_message(
                "Unable to stop agent; its state may have changed."
            )
            return
        scope = (
            'Marcus and child work'
            if conversation_id == (
                self.root_conversation_id or self.conversation_id
            )
            else f'agent {conversation_id[:12]} and child work'
        )
        self.add_system_message(f"Stop requested for {scope}")
        self.update_status("Stopping agent...")

    async def show_agent_tree(self) -> None:
        try:
            conversations = await self._load_agent_tree()
        except (RuntimeError, ValueError) as exc:
            self.add_system_message(escape(str(exc)))
            return
        lines = ['Marcus agent tree:']
        root_id = self.root_conversation_id or self.conversation_id
        for conversation in conversations:
            conversation_id = str(
                conversation.get('uuid') or conversation.get('id') or ''
            )
            role = 'MARCUS' if conversation_id == root_id else 'AGENT'
            status = str(conversation.get('status') or 'unknown').upper()
            topic = str(conversation.get('topic') or 'Untitled')
            lines.append(
                f'{role:<6} {status:<8} {conversation_id[:12]}  {topic[:100]}'
            )
        lines.append(
            'Use /focus <id-prefix> to follow and talk to one agent, '
            '/guide <id-prefix> <message> to steer it without switching, or '
            '/stop <id-prefix> to stop that branch.'
        )
        self.add_system_message(escape('\n'.join(lines)))

    async def focus_agent(self, command: str) -> None:
        parts = command.split(maxsplit=1)
        if len(parts) != 2:
            self.add_system_message(
                'Usage: /focus <conversation-id-prefix|root>'
            )
            return
        reference = parts[1]
        if reference.strip().lower() == 'root':
            reference = self.root_conversation_id
        try:
            conversation_id = await self._resolve_agent_reference(reference)
        except ValueError as exc:
            self.add_system_message(escape(str(exc)))
            return

        self.conversation_id = conversation_id
        self.last_message_key = ''
        self._next_endpoint_status_poll = 0
        self._last_endpoint_status = None
        await self.clear_chat()
        await self.load_conversation_history()
        self.update_status('Focused agent - Ready')

    async def guide_agent(self, command: str) -> None:
        parts = command.split(maxsplit=2)
        if len(parts) != 3 or not parts[2].strip():
            self.add_system_message(
                'Usage: /guide <conversation-id-prefix> <message>'
            )
            return
        try:
            conversation_id = await self._resolve_agent_reference(parts[1])
            await asyncio.to_thread(
                self.sdk.conversations.send_message,
                conversation_id,
                parts[2],
            )
        except (RuntimeError, ValueError) as exc:
            self.add_system_message(escape(str(exc)))
            return
        except Exception:
            self.add_system_message(
                'Unable to deliver guidance; the selected agent may no longer '
                'be active.'
            )
            return
        self.add_system_message(
            f'Guidance queued for agent {conversation_id[:12]}.'
        )

    async def _load_agent_tree(self):
        root_id = self.root_conversation_id or self.conversation_id
        if not root_id:
            raise ValueError('No active Marcus conversation')

        def load():
            records = []
            for conversation_id in self.sdk.conversations.tree_ids(root_id):
                try:
                    metadata = dict(
                        self.sdk.conversations.get_metadata(conversation_id)
                    )
                    metadata.setdefault('uuid', conversation_id)
                    records.append(metadata)
                except Exception:
                    records.append({
                        'uuid': conversation_id,
                        'topic': 'Metadata temporarily unavailable',
                    })
            return records

        return await asyncio.to_thread(load)

    async def _resolve_agent_reference(self, reference):
        root_id = self.root_conversation_id or self.conversation_id
        if not root_id:
            raise ValueError('No active Marcus conversation')
        if reference is None:
            return root_id
        reference = reference.strip().removeprefix('#conversation#')
        if not reference:
            raise ValueError('Conversation ID prefix is required')
        conversation_ids = await asyncio.to_thread(
            self.sdk.conversations.tree_ids,
            root_id,
        )
        exact = next(
            (item for item in conversation_ids if item == reference),
            None,
        )
        if exact:
            return exact
        matches = [
            item for item in conversation_ids if item.startswith(reference)
        ]
        if len(matches) == 1:
            return matches[0]
        if not matches:
            raise ValueError(
                f'Conversation {reference!r} is not in this Marcus agent tree'
            )
        raise ValueError(f'Conversation prefix {reference!r} is ambiguous')
    
    async def send_message(self, message: str) -> None:
        """Send user message and wait for AI response"""
        try:
            # Display user message immediately for instant feedback
            self.add_user_message(message)
            self.update_status("Sending message...")
            
            # Create async task for API call to avoid blocking UI
            async def send_api_request():
                try:
                    # Call API in background
                    response = await asyncio.to_thread(
                        self.call_conversation_api,
                        message,
                    )
                    
                    if response.get('error'):
                        self.add_system_message(f"Error: {response.get('error')}")
                        self.update_status("Error - Ready for next message")
                        return
                    
                    # Update status and wait for AI response
                    self.update_status("Waiting for AI response...")
                    
                    # Poll for AI response
                    await self.wait_for_ai_response()
                    
                except Exception as e:
                    self.add_system_message(f"Failed to send message: {e}")
                    self.update_status("Error - Ready for next message")
            
            # Start the API request as a background task
            asyncio.create_task(send_api_request())
            
        except Exception as e:
            self.add_system_message(f"Failed to send message: {e}")
            self.update_status("Error - Ready for next message")
    
    async def wait_for_ai_response(self) -> None:
        """Wait for AI response and display it"""
        while True:
            # Check for new messages
            await self.check_for_new_messages()
            
            # Check if we got an AI response
            chat_log = self.query_one("#chat-log")
            if chat_log.children and hasattr(chat_log.children[-1], 'role'):
                last_widget = chat_log.children[-1]
                if hasattr(last_widget, 'role') and last_widget.role == "chariot":
                    self.update_status("Ready")
                    break
            
            await asyncio.sleep(1)
    
    async def background_poll(self) -> None:
        """Background polling for job completion events"""
        while True:
            try:
                if self.conversation_id:
                    await self.check_for_new_messages()
                await asyncio.sleep(3)  # Poll every 3 seconds
            except Exception:
                pass
    
    async def check_for_new_messages(self) -> None:
        """Check for new messages once, even with overlapping poll callers."""
        if not self.conversation_id or self._message_poll_lock.locked():
            return

        async with self._message_poll_lock:
            await self.check_endpoint_status()
            try:
                all_messages, _ = await asyncio.to_thread(
                    self.sdk.search.by_key_prefix,
                    f"#message#{self.conversation_id}#",
                    user=True,
                )
                messages = [
                    message for message in all_messages
                    if not self.last_message_key
                    or message.get('key', '') > self.last_message_key
                ]
                messages.sort(key=lambda message: message.get('key', ''))
                for message in messages:
                    self._render_new_message(message)
                if messages:
                    self.last_message_key = messages[-1].get('key', '')
            except Exception:
                pass

            await self.check_for_pending_interaction()

    def _render_new_message(self, message) -> None:
        role = message.get('role')
        content = message.get('content', '')
        if role == 'chariot':
            self.add_ai_message(content)
        elif role == 'tool call':
            tool_name = self._tool_call_name(message)
            self.add_tool_message(f"🔧 Executing {tool_name}...")
            self.update_status(f"Executing {tool_name}...")
        elif role == 'tool response':
            self.add_tool_message("✅ Tool execution completed")
            self.update_status("Tool completed, thinking...")
        elif role == 'planner-output':
            self.add_system_message("🎯 Processing job completion...")

    async def check_endpoint_status(self, force=False) -> None:
        """Render endpoint session/task changes without exposing output tails."""
        now = time.monotonic()
        if not force and now < self._next_endpoint_status_poll:
            return
        self._next_endpoint_status_poll = (
            now + ENDPOINT_STATUS_POLL_INTERVAL_SECONDS
        )
        try:
            status = await asyncio.to_thread(
                self.sdk.endpoint_executions.conversation_status,
                self.conversation_id,
            )
        except Exception:
            return

        fingerprint = endpoint_status_fingerprint(status)
        if fingerprint == self._last_endpoint_status:
            return
        self._last_endpoint_status = fingerprint
        rendered = format_endpoint_execution_status(status)
        if rendered:
            self.add_system_message(escape(rendered))

    async def check_for_pending_interaction(self, force=False) -> None:
        """Show the next approval or credential gate across the agent tree."""
        if not self.conversation_id:
            return

        pending = self._pending_approval or self._pending_credential
        if pending:
            now = time.monotonic()
            if not force and now < self._next_interaction_poll:
                return
            self._next_interaction_poll = (
                now + APPROVAL_POLL_INTERVAL_SECONDS
            )
            if await self._interaction_is_terminal(pending):
                if self._pending_approval is pending:
                    await self._finish_pending_approval(
                        pending,
                        'resolved elsewhere',
                    )
                elif self._pending_credential is pending:
                    await self._finish_pending_credential(
                        pending,
                        'resolved elsewhere',
                    )
            return

        async with self._interaction_lock:
            if self._pending_approval or self._pending_credential:
                return
            now = time.monotonic()
            if not force and now < self._next_interaction_poll:
                return
            self._next_interaction_poll = (
                now + APPROVAL_POLL_INTERVAL_SECONDS
            )
            try:
                interactions = await asyncio.to_thread(
                    self.sdk.conversations.list_interactions,
                    self.root_conversation_id or self.conversation_id,
                    status='pending',
                    include_descendants=True,
                )
            except Exception:
                return

            supported = [
                interaction for kind in ('approval', 'credential')
                for interaction in interactions
                if interaction.get('kind') == kind
            ]
            for interaction in supported:
                request_id = interaction.get('requestId')
                if (
                    not request_id
                    or request_id in self._shown_interaction_ids
                ):
                    continue
                self._shown_interaction_ids.add(request_id)
                if interaction.get('kind') == 'approval':
                    self._show_pending_approval(interaction)
                else:
                    self._show_pending_credential(interaction)
                return

    def _show_pending_approval(self, interaction) -> None:
        self._pending_approval = interaction
        try:
            context = parse_endpoint_approval(interaction)
        except ApprovalContextError as exc:
            self._pending_approval_context = None
            self.add_system_message(
                f'Cannot safely allow endpoint work: {exc}\n'
                'Type "deny" to reject this request.'
            )
        else:
            self._pending_approval_context = context
            self.add_system_message(escape(
                f'{format_endpoint_approval(context)}\n'
                'Type "allow" or "deny".'
            ))
        self.update_status('Endpoint approval required')

    def _show_pending_credential(self, interaction) -> None:
        self._pending_credential = interaction
        self._credential_fields = normalize_credential_interaction_fields(
            interaction.get('fields')
        )
        self._credential_field_index = 0
        self._credential_values.clear()
        request_id = escape(str(interaction.get('requestId') or 'unknown')[:100])
        fields = escape(', '.join(self._credential_fields))
        self.add_system_message(
            f'Credential input required for request {request_id}. '
            f'Requested fields: {fields}. Values are masked, sent once to '
            'the secret broker, and never stored in chat.'
        )
        self._configure_credential_input()
        self.update_status('Credential input required')

    async def answer_pending_approval(self, answer: str) -> None:
        """Submit an explicit allow/deny response for the visible approval."""
        decision = answer.strip().lower()
        if decision not in ('allow', 'deny'):
            choices = '"deny"' if self._pending_approval_context is None else '"allow" or "deny"'
            self.add_system_message(f'Approval pending. Type {choices}.')
            return
        if decision == 'allow' and self._pending_approval_context is None:
            self.add_system_message(
                'This approval has incomplete server context and cannot be allowed. '
                'Type "deny".'
            )
            return

        interaction = self._pending_approval
        response = 'true' if decision == 'allow' else 'false'
        try:
            await asyncio.to_thread(
                self.sdk.conversations.answer_interaction,
                interaction.get('conversationId'),
                interaction.get('requestId'),
                response,
            )
        except Exception as exc:
            if await self._interaction_is_terminal(interaction):
                await self._finish_pending_approval(
                    interaction,
                    'resolved elsewhere',
                )
                return
            self.add_system_message(f'Failed to answer endpoint approval: {exc}')
            return

        outcome = 'allowed' if decision == 'allow' else 'denied'
        await self._finish_pending_approval(interaction, outcome)

    async def answer_pending_credential(self, value: str) -> None:
        """Collect one masked field and submit the completed credential gate."""
        interaction = self._pending_credential
        if interaction is None:
            return
        field = self._credential_fields[self._credential_field_index]
        if not value and not credential_field_is_optional(field):
            self.add_system_message(
                f'A value for {escape(field)} is required.'
            )
            self._configure_credential_input()
            return
        if value:
            self._credential_values[field] = value
        self._credential_field_index += 1
        if self._credential_field_index < len(self._credential_fields):
            self._configure_credential_input()
            return

        values = self._credential_values
        self._credential_values = {}
        messages = []
        try:
            result = await asyncio.to_thread(
                submit_ephemeral_credentials,
                self.sdk,
                interaction,
                dict(values),
                echo=messages.append,
            )
        except Exception:
            values.clear()
            self.add_system_message(
                'Unable to submit credentials securely; values were discarded '
                'and the request remains pending. Re-enter the requested fields.'
            )
            self._credential_field_index = 0
            self._configure_credential_input()
            return
        finally:
            values.clear()

        for message in messages:
            self.add_system_message(message)
        outcome = (
            'resolved elsewhere'
            if result.get('status') in ('answered', 'expired') and messages
            else 'answered'
        )
        await self._finish_pending_credential(interaction, outcome)

    def _configure_credential_input(self) -> None:
        if not self.is_running or not self._pending_credential:
            return
        input_widget = self.query_one("#message-input", Input)
        field = self._credential_fields[self._credential_field_index]
        input_widget.password = True
        input_widget.placeholder = f'Enter {field} securely'
        input_widget.focus()

    def _restore_message_input(self) -> None:
        if not self.is_running:
            return
        input_widget = self.query_one("#message-input", Input)
        input_widget.password = False
        input_widget.placeholder = (
            "Type guidance here... ('stop' cancels the active agent)"
        )
        input_widget.focus()

    async def _interaction_is_terminal(self, interaction) -> bool:
        try:
            current = await asyncio.to_thread(
                self.sdk.conversations.list_interactions,
                interaction.get('conversationId'),
            )
        except Exception:
            return False
        return any(
            row.get('requestId') == interaction.get('requestId')
            and row.get('status') in ('answered', 'expired')
            for row in current
        )

    async def _finish_pending_approval(self, interaction, outcome) -> None:
        if interaction is None or self._pending_approval is not interaction:
            return
        request_id = interaction.get('requestId')
        self._pending_approval = None
        self._pending_approval_context = None
        self.add_system_message(
            f'Endpoint approval {request_id} {outcome}.'
        )
        self.update_status('Waiting for AI response...')
        await self.check_for_pending_interaction(force=True)

    async def _finish_pending_credential(self, interaction, outcome) -> None:
        if interaction is None or self._pending_credential is not interaction:
            return
        request_id = interaction.get('requestId')
        self._pending_credential = None
        self._credential_fields = ()
        self._credential_field_index = 0
        self._credential_values.clear()
        self._restore_message_input()
        self.add_system_message(
            f'Credential request {request_id} {outcome}.'
        )
        self.update_status('Waiting for AI response...')
        await self.check_for_pending_interaction(force=True)
    
    def _tool_call_name(self, message) -> str:
        """Return bounded progress metadata without rendering tool inputs."""
        raw = message.get('toolUseContent') or message.get('content')
        try:
            data = json.loads(raw) if isinstance(raw, str) else raw
        except (TypeError, json.JSONDecodeError):
            data = None
        if not isinstance(data, dict):
            return 'tool'
        name = data.get('Name') or data.get('name') or 'tool'
        tool_input = data.get('Input') or data.get('input')
        detail = None
        if isinstance(tool_input, dict):
            detail = tool_input.get('agent') or tool_input.get('capability')
        label = f'{name}({detail})' if detail else str(name)
        return ''.join(
            character
            for character in label
            if character.isalnum() or character in ' -_.:/()'
        )[:120] or 'tool'

    def add_user_message(self, content: str) -> None:
        """Add user message to chat log"""
        chat_log = self.query_one("#chat-log")
        message_widget = Static(f"👤 You: {content}", classes="user-message")
        chat_log.mount(message_widget)
        chat_log.scroll_end()
    
    def add_ai_message(self, content: str) -> None:
        """Add AI message to chat log"""
        chat_log = self.query_one("#chat-log")
        message_widget = Markdown(content, classes="ai-message")
        message_widget.role = "chariot"  # Add role attribute for tracking
        chat_log.mount(message_widget)
        chat_log.scroll_end()
    
    def add_tool_message(self, content: str) -> None:
        """Add tool execution message to chat log"""
        chat_log = self.query_one("#chat-log")
        message_widget = Static(content, classes="tool-message")
        chat_log.mount(message_widget)
        chat_log.scroll_end()
    
    def add_system_message(self, content: str) -> None:
        """Add system message to chat log"""
        chat_log = self.query_one("#chat-log")
        message_widget = Static(content, classes="system-message")
        chat_log.mount(message_widget)
        chat_log.scroll_end()
    
    def update_status(self, status: str) -> None:
        """Update status bar"""
        status_bar = self.query_one("#status-bar")
        conv_info = f"Conversation: {self.conversation_id[:8]}..." if self.conversation_id else "No conversation"
        status_bar.update(f"User: {self.username} | Mode: {self.mode} | {conv_info} | {status}")
    
    def call_conversation_api(self, message: str) -> Dict:
        """Call the Chariot conversation API"""
        url = self.sdk.url("/planner")
        payload = {"message": message, "mode": self.mode}
        
        if self.conversation_id:
            payload["conversationId"] = self.conversation_id
        
        response = self.sdk.chariot_request("POST", url, json=payload)
        
        if response.status_code == 200:
            result = response.json()
            
            if not self.conversation_id and 'conversation' in result:
                self.conversation_id = result['conversation'].get('uuid')
                self.root_conversation_id = self.conversation_id
                self.update_status("Ready")
            
            return {'success': True}
        else:
            return {
                'success': False,
                'error': f"API error: {response.status_code} - {response.text}"
            }
    
    def show_help(self) -> None:
        """Show help information"""
        help_text = """
# Available Commands:
- `help` - Show this help
- `clear` - Clear chat log
- `new` - Start new conversation
- `resume` - Resume existing conversation
- `query` - Switch to Query Mode (data discovery only)
- `agent` - Switch to Agent Mode (full security operations)
- `jobs` - Show running jobs
- `/agents` - Show Marcus and every delegated agent
- `/focus <id-prefix|root>` - Follow and talk directly to one agent
- `/guide <id-prefix> <message>` - Steer one active agent without switching
- `/stop <id-prefix>` - Stop one agent branch
- `stop` - Stop Marcus and all correlated child work (`Ctrl+X`)
- `quit` - Exit

# Query Mode:
- Search and analyze existing security data
- List available capabilities
- Data discovery focus

# Agent Mode:
- Full security operations with live tool progress
- Send guidance while Marcus or a subagent is running
- Review endpoint actions before execution
- Supply masked, one-time credentials for HITL agents
- Stop Marcus and correlated child work at any time

# Examples:
- "Find all active assets"
- "Show me high-priority risks" 
- "Run a port scan on 10.0.1.5" (agent mode only)
- "Use HITL Romulus against the authorized web application; prompt me for login and MFA"
        """
        self.add_system_message(help_text)
    
    def set_mode(self, mode: str) -> None:
        """Switch conversation mode"""
        if mode in ["query", "agent"]:
            self.mode = mode
            self.update_status("Ready")
            if mode == "query":
                self.add_system_message("Switched to Query Mode - Data discovery and analysis focus")
            elif mode == "agent":
                self.add_system_message("Switched to Agent Mode - Full security operations")
        else:
            self.add_system_message(f"Invalid mode: {mode}. Available modes: query, agent")

    def _reset_interaction_state(self) -> None:
        self._pending_approval = None
        self._pending_approval_context = None
        self._pending_credential = None
        self._credential_fields = ()
        self._credential_field_index = 0
        self._credential_values.clear()
        self._shown_interaction_ids.clear()
        self._next_interaction_poll = 0
        self._restore_message_input()
    
    async def start_new_conversation(self) -> None:
        """Start a new conversation"""
        self.conversation_id = None
        self.root_conversation_id = None
        self.last_message_key = ""
        self._reset_interaction_state()
        self._next_endpoint_status_poll = 0
        self._last_endpoint_status = None
        await self.clear_chat()
        self.add_system_message("Started new conversation")
        self.update_status("Ready")
    
    async def resume_conversation(self) -> None:
        """Resume an existing conversation"""
        try:
            # Get recent conversations without blocking the Textual event loop.
            conversations, _ = await asyncio.to_thread(
                self.sdk.search.by_key_prefix,
                "#conversation#",
                user=True,
            )
            conversations = sorted(conversations, key=lambda x: x.get('created', ''), reverse=True)
            
            if not conversations:
                self.add_system_message("No recent conversations found. Starting new conversation.")
                await self.start_new_conversation()
                return
            
            # Show beautiful conversations table
            conv_list = f"""
# 💬 Resume Conversation

**Found {len(conversations)} recent conversations**

```
┌─────────────────────────────────────────────────────────────────┐
│                      RECENT CONVERSATIONS                       │
├─────────────────────────────────────────────────────────────────┤
"""
            
            for i, conv in enumerate(conversations[:10]):
                topic = conv.get('topic', 'No topic')
                # Truncate topic but show more characters
                if len(topic) > 45:
                    topic = topic[:42] + "..."
                
                created = conv.get('created', 'Unknown')
                # Format date more nicely
                if created != 'Unknown':
                    try:
                        # Parse and format the date
                        if 'T' in created:
                            dt = datetime.fromisoformat(created.replace('Z', '+00:00'))
                            created = dt.strftime('%m/%d %H:%M')
                        else:
                            created = created[:10]  # Just date part
                    except:
                        created = created[:16]
                
                conv_list += f"│ {i+1:2}. 💭 {topic:<45} │ {created:<10} │\n"
                conv_list += f"│{'':<65}│\n"
            
            conv_list += f"""├─────────────────────────────────────────────────────────────────┤
│  Type a number (1-{len(conversations[:10])}) to resume, or 'new' to start fresh   │
└─────────────────────────────────────────────────────────────────┘
```"""
            
            self.add_system_message(conv_list)
            
            # Store conversations for selection
            self._available_conversations = conversations[:10]
            self._selecting_conversation = True
            
        except Exception as e:
            self.add_system_message(f"Error loading conversations: {e}")
            await self.start_new_conversation()
    
    async def handle_conversation_selection(self, selection: str) -> None:
        """Handle conversation selection by number"""
        # Handle non-numeric inputs first
        if selection.lower() in ['new', 'cancel']:
            self._selecting_conversation = False
            self._available_conversations = []
            await self.start_new_conversation()
            return
            
        # Try to parse as number
        try:
            conv_index = int(selection) - 1
            if 0 <= conv_index < len(self._available_conversations):
                selected_conv = self._available_conversations[conv_index]
                self.conversation_id = selected_conv['uuid']
                try:
                    self.root_conversation_id = await asyncio.to_thread(
                        self.sdk.conversations.root_id,
                        self.conversation_id,
                    )
                except Exception:
                    self.root_conversation_id = self.conversation_id
                self.last_message_key = ""
                self._reset_interaction_state()
                self._next_endpoint_status_poll = 0
                self._last_endpoint_status = None
                self._selecting_conversation = False
                self._available_conversations = []
                
                await self.clear_chat()
                self.add_system_message(f"Resumed conversation: {selected_conv.get('topic', 'No topic')}")
                
                # Load conversation history
                await self.load_conversation_history()
                self.update_status("Ready")
            else:
                self.add_system_message(f"Invalid selection. Please choose 1-{len(self._available_conversations)} or type 'new' to cancel.")
                
        except ValueError:
            self.add_system_message("Invalid input. Please enter a number or type 'new' to cancel.")
    
    async def load_conversation_history(self) -> None:
        """Load and display conversation history"""
        if not self.conversation_id:
            return
            
        try:
            # Load all messages for this conversation.
            messages, _ = await asyncio.to_thread(
                self.sdk.search.by_key_prefix,
                f"#message#{self.conversation_id}#",
                user=True,
            )
            messages = sorted(messages, key=lambda x: x.get('key', ''))
            
            self.add_system_message(f"Loading {len(messages)} messages from conversation history...")
            
            for msg in messages:
                role = msg.get('role')
                content = msg.get('content', '')
                
                if role == 'user':
                    self.add_user_message(content)
                elif role == 'chariot':
                    self.add_ai_message(content)
                elif role == 'tool call':
                    self.add_tool_message(
                        f"🔧 Executed {self._tool_call_name(msg)}"
                    )
                elif role == 'tool response':
                    self.add_tool_message("✅ Tool execution completed")
                elif role == 'planner-output':
                    self.add_system_message("🎯 Job completion processed")
            
            # Set last message key for future polling
            if messages:
                self.last_message_key = messages[-1].get('key', '')
                
            self.add_system_message("Conversation history loaded. You can continue the conversation.")
            
        except Exception as e:
            self.add_system_message(f"Error loading conversation history: {e}")
    
    async def clear_chat(self) -> None:
        """Clear the chat log"""
        chat_log = self.query_one("#chat-log")
        await chat_log.remove_children()
    
    async def show_job_status(self) -> None:
        """Show active jobs for the current conversation"""
        if not self.conversation_id:
            self.add_system_message("No active conversation")
            return
            
        try:
            jobs, _ = await asyncio.to_thread(
                self.sdk.search.by_term,
                f"conversation:{self.conversation_id}",
            )
            jobs = jobs if jobs else []
            
            if not jobs:
                self.add_system_message("No jobs found for this conversation")
                return
            
            # Create beautiful jobs table
            job_summary = f"""
# 🚀 Security Jobs Status

**Conversation Jobs: {len(jobs)}**

```
┌─────────────────────────────────────────────────────────────────┐
│                        ACTIVE SECURITY JOBS                     │
├─────────────────────────────────────────────────────────────────┤
"""
            
            for i, job in enumerate(jobs, 1):
                status = job.get('status', '')
                capability = job.get('source', 'unknown')
                
                # Extract target from job key
                job_key = job.get('key', '')
                if job_key.startswith('#job#'):
                    parts = job_key.split('#')
                    if len(parts) >= 3:
                        target_part = parts[2]
                        if target_part.startswith('#asset#'):
                            asset_parts = target_part.split('#')
                            target_display = asset_parts[3] if len(asset_parts) >= 4 else target_part
                        else:
                            target_display = target_part
                    else:
                        target_display = job_key
                else:
                    target_display = job.get('dns', 'unknown')
                
                # Map status to readable format with better emojis
                status_info = {
                    'JQ': ('🔵', 'QUEUED', 'Waiting to start'),
                    'JR': ('🟡', 'RUNNING', 'Currently executing'), 
                    'JP': ('🟢', 'COMPLETED', 'Successfully finished'),
                    'JF': ('🔴', 'FAILED', 'Execution failed')
                }
                
                emoji, status_name, description = status_info.get(status[:2], ('⚪', 'UNKNOWN', 'Status unknown'))
                
                # Format each job entry nicely
                job_summary += f"│ {i:2}. {emoji} {status_name:<9} │ {capability:<15} │ {target_display:<25} │\n"
                if len(jobs) <= 5:  # Show descriptions for small lists
                    job_summary += f"│     {description:<60} │\n"
                job_summary += f"│{'':<65}│\n"
            
            job_summary += "└─────────────────────────────────────────────────────────────────┘\n```"
            
            self.add_system_message(job_summary)
            
        except Exception as e:
            self.add_system_message(f"Failed to get job status: {e}")


def run_textual_conversation(sdk: Chariot, mode: str = "query") -> None:
    """Run the Textual-based conversation interface."""
    app = ConversationApp(sdk, mode=mode)
    app.run()