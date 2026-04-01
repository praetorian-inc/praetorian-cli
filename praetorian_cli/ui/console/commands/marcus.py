"""Marcus AI commands: ask/marcus/read/ingest/do. Mixed into GuardConsole."""

import json
import os
import time
from typing import Optional

from prompt_toolkit.formatted_text import HTML
from rich.markdown import Markdown
from rich.panel import Panel

from praetorian_cli.ui.aegis.theme import PRIMARY_RED, COMPLEMENTARY_GOLD


class MarcusCommands:
    """Marcus AI console commands. Mixed into GuardConsole."""

    def _cmd_ask(self, args):
        if not args:
            self.console.print('[dim]Usage: ask "<question>"[/dim]')
            return

        message = ' '.join(args)
        if message.startswith('--new'):
            self.context.clear_conversation()
            message = ' '.join(args[1:])

        message = self.context.apply_scope_to_message(message)
        response_text = self._send_to_marcus(message)

        if response_text:
            self.console.print(Panel(
                Markdown(response_text),
                title='Marcus',
                border_style=self.colors['primary'],
            ))

    def _cmd_marcus(self, args):
        """Marcus subcommands or multi-turn conversation mode."""
        # Handle subcommands: marcus read, marcus ingest, marcus do
        if args and args[0].lower() == 'read':
            self._marcus_read(args[1:])
            return
        if args and args[0].lower() == 'ingest':
            self._marcus_ingest(args[1:])
            return
        if args and args[0].lower() == 'do':
            self._marcus_do(args[1:])
            return
        if args and args[0].lower() == 'research':
            self._cmd_critfinder(args[1:])
            return

        if args and args[0] == '--new':
            self.context.clear_conversation()
        if args and args[0] == '--query':
            self.context.mode = 'query'

        self.console.print(f'[primary]Entering conversation mode[/primary] [dim](type "/back" to return)[/dim]')
        self.console.print(f'[dim]Commands: /back, /new, /query, /agent, or just chat[/dim]')
        self.console.print(f'[dim]Context: {self.context.summary()}[/dim]\n')

        while True:
            try:
                marcus_prompt = HTML(
                    f'<style fg="{COMPLEMENTARY_GOLD}" bg="">marcus</style>'
                    f' <style fg="{PRIMARY_RED}" bg="">&gt;</style> '
                )
                user_input = self.session.prompt(marcus_prompt).strip()
            except (KeyboardInterrupt, EOFError):
                break

            if not user_input:
                continue

            # Slash commands for conversation control
            if user_input.startswith('/'):
                slash_cmd = user_input[1:].lower().split()[0] if user_input[1:] else ''
                if slash_cmd in ('back', 'quit', 'exit'):
                    break
                elif slash_cmd == 'new':
                    self.context.clear_conversation()
                    self.console.print('[success]New conversation started[/success]')
                    continue
                elif slash_cmd in ('query', 'agent'):
                    self.context.mode = slash_cmd
                    self.console.print(f'[success]Switched to {slash_cmd} mode[/success]')
                    continue
                else:
                    self.console.print(f'[dim]Unknown command: /{slash_cmd}. Use /back, /new, /query, /agent[/dim]')
                    continue

            # Everything else is sent to Marcus as a message
            message = self.context.apply_scope_to_message(user_input)
            response_text = self._send_to_marcus(message)
            if response_text:
                self.console.print(Markdown(response_text))
                self.console.print()

        self.console.print('[dim]Returned to console.[/dim]')

    def _send_to_marcus(self, message: str) -> Optional[str]:
        """Send message to Marcus and poll for response with live tool output."""
        url = self.sdk.url('/planner')
        payload = {'message': message, 'mode': self.context.mode}
        if self.context.conversation_id:
            payload['conversationId'] = self.context.conversation_id

        with self.console.status('Sending...', spinner='dots', spinner_style=self.colors['primary']):
            response = self.sdk.chariot_request('POST', url, json=payload)

        # If AI is disabled on the impersonated account, retry as the Praetorian user
        if response.status_code == 403 and self.context.account:
            login_user = self.sdk.accounts.login_principal()
            if login_user and login_user.endswith('@praetorian.com'):
                self.console.print(f'[dim]AI not enabled on this account -- routing through {login_user}[/dim]')
                # Temporarily clear impersonation for the AI call
                saved_account = self.sdk.keychain.account
                self.sdk.keychain.account = None
                # Add engagement context to the message so Marcus queries the right data
                if self.context.account not in message:
                    message = f'[Context: querying data for account {self.context.account}] {message}'
                payload['message'] = message
                if self.context.conversation_id:
                    payload.pop('conversationId', None)
                    self.context.conversation_id = None
                with self.console.status('Sending via Praetorian account...', spinner='dots', spinner_style=self.colors['primary']):
                    response = self.sdk.chariot_request('POST', url, json=payload)
                self.sdk.keychain.account = saved_account

        if not response.ok:
            self.console.print(f'[error]API error: {response.status_code} - {response.text}[/error]')
            return None

        result = response.json()
        if not self.context.conversation_id and 'conversation' in result:
            self.context.conversation_id = result['conversation'].get('uuid')

        # Snapshot existing messages so we only process NEW ones from this request
        last_key = ''
        try:
            existing, _ = self.sdk.search.by_key_prefix(
                f'#message#{self.context.conversation_id}#', user=True
            )
            if existing:
                last_key = max(m.get('key', '') for m in existing)
        except Exception:
            pass

        # Poll for response -- show tool calls live
        max_wait = 180
        start_time = time.time()
        pending_tool = None

        self.console.print(f'[dim]Thinking...[/dim]', end='')

        while time.time() - start_time < max_wait:
            try:
                messages, _ = self.sdk.search.by_key_prefix(
                    f'#message#{self.context.conversation_id}#', user=True
                )
                new_msgs = sorted(
                    [m for m in messages if m.get('key', '') > last_key],
                    key=lambda x: x.get('key', '')
                )

                for msg in new_msgs:
                    role = msg.get('role', '')
                    content = msg.get('content', '')
                    last_key = msg.get('key', '')

                    if role == 'chariot':
                        if pending_tool:
                            self.console.print()  # newline after tool output
                        return content
                    elif role == 'tool call':
                        # Parse tool call content for display
                        tool_name = self._parse_tool_name(content, msg)
                        if pending_tool:
                            self.console.print(f' [success]done[/success]')
                        self.console.print(f'  [dim]->[/dim] [accent]{tool_name}[/accent]', end='')
                        pending_tool = tool_name
                    elif role == 'tool response':
                        # Show result summary
                        result_summary = self._parse_tool_result(content)
                        if result_summary:
                            self.console.print(f' [dim]-- {result_summary}[/dim]', end='')
                        self.console.print(f' [success]done[/success]')
                        pending_tool = None
            except Exception:
                pass

            time.sleep(1)

        self.console.print('\n[warning]Timed out waiting for response[/warning]')
        return None

    def _parse_tool_name(self, content: str, msg: dict = None) -> str:
        """Extract a human-readable tool name from a tool call message."""
        # Try toolUseContent field first (structured tool input)
        tool_content = msg.get('toolUseContent', '') if msg else ''
        # Try the message name field (some backends store tool name there)
        msg_name = msg.get('name', '') if msg else ''
        if msg_name and msg_name not in ('user', 'chariot', 'tool call', 'tool response'):
            return msg_name

        for raw in (tool_content, content):
            if not raw:
                continue
            try:
                data = json.loads(raw) if isinstance(raw, str) else raw
                if isinstance(data, dict):
                    name = data.get('name', data.get('tool', data.get('type', '')))
                    if name:
                        inp = data.get('input', data.get('arguments', {}))
                        if isinstance(inp, dict):
                            if 'capability' in inp:
                                return f'{name}({inp["capability"]})'
                            if 'agent' in inp:
                                return f'{name}({inp["agent"]})'
                        return str(name)
            except (json.JSONDecodeError, TypeError, AttributeError):
                continue
        return 'tool'

    def _parse_tool_result(self, content: str) -> str:
        """Extract a brief summary from a tool response message."""
        try:
            data = json.loads(content) if isinstance(content, str) else content
            if isinstance(data, dict):
                # Count results if it looks like a query response
                for key in ('assets', 'risks', 'data', 'results', 'seeds', 'jobs'):
                    if key in data and isinstance(data[key], list):
                        return f'{len(data[key])} {key}'
                if 'status' in data:
                    return f'status: {data["status"]}'
                if 'error' in data:
                    return f'error: {str(data["error"])[:50]}'
            elif isinstance(data, list):
                return f'{len(data)} results'
        except (json.JSONDecodeError, TypeError, AttributeError):
            pass
        return ''

    def _marcus_read(self, args):
        """Have Marcus read and analyze a file."""
        if not args:
            self.console.print('[dim]Usage: marcus read <guard_path> [--local][/dim]')
            self.console.print('[dim]  guard_path: file in Guard storage (e.g., vault/sow.pdf, proofs/screenshot.png)[/dim]')
            self.console.print('[dim]  --local: path is a local file (uploads to Guard first)[/dim]')
            return

        path = args[0]
        is_local = '--local' in args
        instructions = ''
        if '-i' in args:
            idx = args.index('-i')
            if idx + 1 < len(args):
                instructions = ' '.join(args[idx + 1:])

        if is_local:
            if not os.path.exists(path):
                self.console.print(f'[error]Local file not found: {path}[/error]')
                return
            filename = os.path.basename(path)
            guard_path = f'home/{filename}'
            with self.console.status(f'Uploading {path}...', spinner='dots', spinner_style=self.colors['primary']):
                self.sdk.files.add(path, guard_path)
            self.console.print(f'[success]Uploaded to {guard_path}[/success]')
            path = guard_path

        base = f'Read the file at "{path}" using the file_read tool.'
        if instructions:
            message = f'{base} {instructions}'
        else:
            message = (
                f'{base} Analyze its contents and tell me what you found. '
                f'If it contains scope info (domains, IPs, CIDRs), offer to add them as seeds. '
                f'If it contains vulnerability findings, offer to create risks. '
                f'If it contains credentials or secrets, flag them.'
            )

        message = self.context.apply_scope_to_message(message)
        response = self._send_to_marcus(message)
        if response:
            self.console.print(Panel(Markdown(response), title='Marcus', border_style=self.colors['primary']))

    def _marcus_ingest(self, args):
        """Have Marcus read a file and automatically ingest data into Guard."""
        if not args:
            self.console.print('[dim]Usage: marcus ingest <guard_path> [--scope] [--findings][/dim]')
            return

        path = args[0]
        scope = '--scope' in args
        findings = '--findings' in args

        actions = []
        if scope:
            actions.append('Add any discovered domains, IPs, and CIDRs as seeds using seed_add.')
        if findings:
            actions.append('Create risks for any vulnerability findings you identify.')
        if not actions:
            actions.append('Add scope items as seeds and create risks for any findings.')

        message = (
            f'Read the file at "{path}" using the file_read tool. '
            f'Analyze its contents thoroughly. {" ".join(actions)} '
            f'Take action automatically -- do not ask for confirmation. '
            f'Report what you created when done.'
        )

        message = self.context.apply_scope_to_message(message)
        self.console.print(f'[info]Marcus is reading and ingesting {path}...[/info]')
        response = self._send_to_marcus(message)
        if response:
            self.console.print(Panel(Markdown(response), title='Marcus -- Ingestion Complete', border_style=self.colors['primary']))

    def _marcus_do(self, args):
        """Give Marcus a direct instruction to execute."""
        if not args:
            self.console.print('[dim]Usage: marcus do "<instruction>"[/dim]')
            self.console.print('[dim]  Examples:[/dim]')
            self.console.print('[dim]    marcus do "add example.com as a seed and start discovery"[/dim]')
            self.console.print('[dim]    marcus do "run nuclei on all assets with port 443"[/dim]')
            self.console.print('[dim]    marcus do "generate an executive summary"[/dim]')
            return

        instruction = ' '.join(args)
        message = self.context.apply_scope_to_message(instruction)
        response = self._send_to_marcus(message)
        if response:
            self.console.print(Panel(Markdown(response), title='Marcus', border_style=self.colors['primary']))

    def _cmd_critfinder(self, args):
        """Run CritFinder adversarial vulnerability research pipeline."""
        from praetorian_cli.handlers.critfinder import _build_research_message, _stream_research, _colorize_progress
        import shlex

        # Parse args
        tokens = shlex.split(' '.join(args)) if args else []
        target = None
        depth = 1
        novel = False
        research_mode = 'offensive'

        i = 0
        while i < len(tokens):
            if tokens[i] == '--depth' and i + 1 < len(tokens):
                try:
                    depth = int(tokens[i + 1])
                except ValueError:
                    self.console.print('[error]--depth must be an integer[/error]')
                    return
                i += 2
            elif tokens[i] == '--novel':
                novel = True
                i += 1
            elif tokens[i] == '--mode' and i + 1 < len(tokens):
                research_mode = tokens[i + 1]
                if research_mode not in ('offensive', 'knowledge'):
                    self.console.print('[error]--mode must be "offensive" or "knowledge"[/error]')
                    return
                i += 2
            elif tokens[i] == '--help':
                self.console.print('[dim]Usage: critfinder [target] [--depth N] [--novel] [--mode offensive|knowledge][/dim]')
                self.console.print('[dim]  Run CritFinder adversarial vulnerability research pipeline.[/dim]')
                self.console.print('[dim]  Aliases: critfinder, research, hunt[/dim]')
                self.console.print()
                self.console.print('[dim]  Examples:[/dim]')
                self.console.print('[dim]    critfinder                          # full engagement scan[/dim]')
                self.console.print('[dim]    critfinder k8s.client.com           # scoped to target[/dim]')
                self.console.print('[dim]    critfinder --depth 3                # iterative deep hunt[/dim]')
                self.console.print('[dim]    critfinder --novel                  # 0day hunting mode[/dim]')
                self.console.print('[dim]    critfinder --mode knowledge CVE-2024-1234[/dim]')
                return
            elif not tokens[i].startswith('-'):
                target = tokens[i]
                i += 1
            else:
                self.console.print(f'[error]Unknown option: {tokens[i]}[/error]')
                return

        message = _build_research_message(target, depth, novel, research_mode)

        # Apply engagement scope context
        message = self.context.apply_scope_to_message(message)

        self.console.print('[bold]CritFinder[/bold] — Adversarial Vulnerability Research Pipeline')
        self.console.print('─' * 60)
        if target:
            self.console.print(f'Target: {target}')
        else:
            self.console.print('Target: full engagement (auto-select)')
        self.console.print(f'Mode: {"novel" if novel else research_mode}')
        self.console.print(f'Depth: {depth} cycle{"s" if depth > 1 else ""}')
        self.console.print('─' * 60)
        self.console.print()

        _stream_research(self.sdk, message)

    def _cmd_research(self, args):
        """Alias for critfinder."""
        self._cmd_critfinder(args)

    def _cmd_hunt(self, args):
        """Alias for critfinder."""
        self._cmd_critfinder(args)
