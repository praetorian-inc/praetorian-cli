"""Marcus AI commands: ask/marcus/read/ingest/do. Mixed into GuardConsole."""

import json
import os
import time
from typing import Optional

from requests.exceptions import RequestException

from prompt_toolkit.formatted_text import HTML
from rich.markdown import Markdown
from rich.panel import Panel

from praetorian_cli.ui.aegis.theme import PRIMARY_RED, COMPLEMENTARY_GOLD


class MarcusError(Exception):
    """Raised for recoverable Marcus terminal errors (shown to the user)."""


class _WSUnavailable(Exception):
    """Internal: WebSocket transport unavailable; fall back to polling."""


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
            panel_title = f'Marcus @ {self.context.account}' if self.context.account else 'Marcus'
            self.console.print(Panel(
                Markdown(response_text),
                title=panel_title,
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

        self.console.print('[primary]Entering conversation mode[/primary] [dim](type "/back" to return)[/dim]')
        self.console.print(f'[dim]Commands: /back, /new, /query, /agent, /skill <path>, /skills, /unskill <name>, or just chat[/dim]')
        self.console.print(f'[dim]Context: {self.context.summary()}[/dim]')
        if self.context.skills:
            self.console.print(f'[dim]Skills: {", ".join(os.path.basename(s) for s in self.context.skills)}[/dim]')
        if not self.context.account:
            self.console.print(f'[warning]No account set -- Marcus will query your personal account. Use "set account <email>" first.[/warning]')
        self.console.print()

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
                elif slash_cmd == 'skill':
                    parts = user_input[1:].split(None, 1)
                    if len(parts) < 2:
                        self.console.print('[dim]Usage: /skill <path-to-skill-file>[/dim]')
                        continue
                    try:
                        name = self.context.load_skill(parts[1].strip())
                        self.console.print(f'[success]Loaded skill: {name}[/success]')
                    except (FileNotFoundError, ValueError) as e:
                        self.console.print(f'[error]{e}[/error]')
                    continue
                elif slash_cmd == 'skills':
                    if self.context.skills:
                        self.console.print('[primary]Active skills:[/primary]')
                        for s in self.context.skills:
                            self.console.print(f'  [accent]{os.path.basename(s)}[/accent] [dim]({s})[/dim]')
                    else:
                        self.console.print('[dim]No skills loaded. Use /skill <path> to load one.[/dim]')
                    continue
                elif slash_cmd == 'unskill':
                    parts = user_input[1:].split(None, 1)
                    if len(parts) < 2:
                        self.console.print('[dim]Usage: /unskill <name-or-path>[/dim]')
                        continue
                    if self.context.unload_skill(parts[1].strip()):
                        self.console.print(f'[success]Unloaded skill: {parts[1].strip()}[/success]')
                    else:
                        self.console.print(f'[warning]Skill not found: {parts[1].strip()}[/warning]')
                    continue
                else:
                    self.console.print(f'[dim]Unknown command: /{slash_cmd}. Use /back, /new, /query, /agent, /skill, /skills, /unskill[/dim]')
                    continue

            # Everything else is sent to Marcus as a message
            message = self.context.apply_scope_to_message(user_input)
            response_text = self._send_to_marcus(message)
            if response_text:
                self.console.print(Markdown(response_text))
                self.console.print()

        self.console.print('[dim]Returned to console.[/dim]')

    def _post_to_planner(self, message: str):
        """POST to /planner, handling the 403 retry-as-Praetorian path safely.

        Returns the parsed JSON dict. Raises on network/HTTP error; the keychain
        account is always restored.
        """
        message = self.context.apply_skills_to_message(message)
        url = self.sdk.url('/planner')
        payload = {'message': message, 'mode': self.context.mode}
        if self.context.conversation_id:
            payload['conversationId'] = self.context.conversation_id

        with self.console.status('Sending...', spinner='dots',
                                 spinner_style=self.colors['primary']):
            try:
                response = self.sdk.chariot_request('POST', url, json=payload)
            except RequestException as e:
                raise MarcusError(f'Network error reaching Marcus: {e}')

        if response.status_code == 403 and self.context.account:
            login_user = self.sdk.accounts.login_principal()
            if login_user and login_user.endswith('@praetorian.com'):
                self.console.print(
                    f'[dim]AI not enabled on this account -- routing through {login_user}[/dim]')
                saved_account = self.sdk.keychain.account
                try:
                    self.sdk.keychain.account = None
                    if self.context.account not in message:
                        message = f'[Context: querying data for account {self.context.account}] {message}'
                    payload['message'] = message
                    if self.context.conversation_id:
                        payload.pop('conversationId', None)
                        self.context.conversation_id = None
                    with self.console.status('Sending via Praetorian account...', spinner='dots',
                                             spinner_style=self.colors['primary']):
                        try:
                            response = self.sdk.chariot_request('POST', url, json=payload)
                        except RequestException as e:
                            raise MarcusError(f'Network error reaching Marcus: {e}')
                finally:
                    self.sdk.keychain.account = saved_account

        if not response.ok:
            raise MarcusError(f'API error: {response.status_code} - {response.text}')

        try:
            return response.json()
        except (ValueError, json.JSONDecodeError):
            raise MarcusError(
                f'Unexpected non-JSON response ({response.status_code}): {response.text[:200]}')

    def _snapshot_last_key(self, conversation_id: Optional[str]) -> str:
        """Return the highest existing message key for a conversation, or '' if none/unknown."""
        if not conversation_id:
            return ''
        try:
            existing, _ = self.sdk.search.by_key_prefix(
                f'#message#{conversation_id}#', user=True
            )
            if existing:
                return max(m.get('key', '') for m in existing)
        except Exception:
            pass
        return ''

    def _send_to_marcus(self, message: str) -> Optional[str]:
        """Send message to Marcus and poll for response with live tool output."""
        # Snapshot existing messages BEFORE the POST so we only process NEW ones
        # from this request — capturing it after the POST risks missing messages
        # when the response comes back fast. New conversations have no prior
        # messages to snapshot, so they start from after_key=''.
        pre_conversation_id = self.context.conversation_id
        last_key = self._snapshot_last_key(pre_conversation_id)

        try:
            result = self._post_to_planner(message)
        except KeyboardInterrupt:
            self.console.print('\n[warning]Cancelled — returned to console.[/warning]')
            return None
        except MarcusError as e:
            self.console.print(f'[error]{e}[/error]')
            return None

        if isinstance(result, dict) and not self.context.conversation_id and 'conversation' in result:
            self.context.conversation_id = result['conversation'].get('uuid')

        # A 403 retry inside _post_to_planner may have cleared conversation_id and
        # started a brand-new conversation on the reroute. In that case the
        # pre-POST snapshot above belongs to the OLD conversation's key namespace
        # and must not be reused as after_key for the new one — re-snapshot
        # against the finalized conversation_id.
        if pre_conversation_id and self.context.conversation_id != pre_conversation_id:
            last_key = self._snapshot_last_key(self.context.conversation_id)

        acct_label = f' [dim]({self.context.account})[/dim]' if self.context.account else ''
        self.console.print(f'[dim]Thinking...[/dim]{acct_label}')
        tool_log = []
        try:
            for msg in self._stream_messages(self.context.conversation_id, after_key=last_key):
                role = msg.get('role', '')
                content = msg.get('content', '')
                if role == 'chariot':
                    self._last_tool_log = tool_log
                    return content
                elif role == 'tool call':
                    tool_name = self._parse_tool_name(content, msg)
                    tool_log.append({'role': role, 'name': tool_name, 'content': content,
                                     'msg': msg, 'key': msg.get('key', '')})
                    self.console.print(f'  [dim]->[/dim] [accent]{tool_name}[/accent]')
                    if self.context.verbose:
                        self._print_verbose_tool_call(content, msg)
                elif role == 'tool response':
                    result_summary = self._parse_tool_result(content)
                    inferred = self._infer_tool_from_response(content)
                    tool_log.append({'role': role, 'name': inferred, 'content': content,
                                     'summary': result_summary, 'key': msg.get('key', '')})
                    if result_summary:
                        self.console.print(f'    [dim]-- {result_summary}[/dim] [success]done[/success]')
                    else:
                        self.console.print(f'    [success]done[/success]')
                    if self.context.verbose:
                        self._print_verbose_tool_response(content)
        except KeyboardInterrupt:
            self._last_tool_log = tool_log
            self.console.print('\n[warning]Cancelled — returned to console.[/warning]')
            return None
        except MarcusError as e:
            self._last_tool_log = tool_log
            self.console.print(f'\n[error]{e}[/error]')
            return None
        self._last_tool_log = tool_log
        return None

    def _poll_messages(self, conversation_id, after_key='', *, max_wait=180,
                       sleep=time.sleep, error_threshold=5):
        """Yield new conversation messages in key order until a 'chariot' reply.

        Fetches the conversation and filters client-side for messages after `after_key`. Backs off when idle. Raises
        MarcusError after `error_threshold` consecutive fetch failures so
        problems surface instead of hanging.
        """
        start = time.time()
        last_key = after_key
        delay = 1.0
        consecutive_errors = 0
        prefix = f'#message#{conversation_id}#'
        while time.time() - start < max_wait:
            try:
                messages, _ = self.sdk.search.by_key_prefix(prefix, user=True)
                consecutive_errors = 0
            except Exception as e:
                consecutive_errors += 1
                if consecutive_errors >= error_threshold:
                    raise MarcusError(f'Lost connection while waiting for Marcus: {e}')
                sleep(delay)
                continue
            new = sorted((m for m in messages if isinstance(m, dict) and m.get('key', '') > last_key),
                         key=lambda x: x.get('key', ''))
            if new:
                delay = 1.0
                for msg in new:
                    last_key = msg.get('key', '')
                    yield msg
                    if msg.get('role', '') == 'chariot':
                        return
            else:
                delay = min(delay + 1.0, 3.0)
            sleep(delay)
        raise MarcusError('Timed out waiting for response')

    def _ws_messages(self, conversation_id, after_key='', *, max_wait=180):
        """Yield new conversation messages via the WebSocket change-feed until a
        'chariot' reply. Reuses by_key_prefix to fetch message bodies on each WS
        event. Raises MarcusError on timeout. Raises _WSUnavailable on
        connect/subscribe failure so the caller can fall back to polling."""
        import websocket  # websocket-client
        ws_url = self.sdk.keychain.websocket_url()
        token = self.sdk.keychain.token()
        # Token is embedded as a query-string parameter — must never be logged or
        # interpolated into exception messages.
        url = f"{ws_url}?token={token}&user=true"
        # Unlike _post_to_planner, the WS path does not perform the 403 "route
        # through @praetorian.com" reroute — it assumes the account has direct AI
        # access (opt-in transport).
        if self.sdk.keychain.account:
            url += f"&account={self.sdk.keychain.account}"
        try:
            conn = websocket.create_connection(url, timeout=10)
            conn.send(json.dumps({"action": "subscribe", "subscriptions": [
                {"pattern": f"#message#{conversation_id}", "matchType": "prefix"}]}))
        except Exception as e:
            # str(e) from websocket-client does not contain the URL/token, so
            # this is safe; the URL variable is intentionally not interpolated here.
            raise _WSUnavailable(str(e))
        last_key = after_key
        start = time.time()
        yielded = False
        try:
            while time.time() - start < max_wait:
                try:
                    conn.settimeout(5)
                    conn.recv()  # block until a change event (content ignored; signal only)
                except websocket.WebSocketTimeoutException:
                    pass  # 5 s timeout doubles as an idle safety re-poll (intentional)
                except Exception as e:
                    # str(e) does not contain the URL/token — safe to forward as-is.
                    raise _WSUnavailable(str(e))
                try:
                    messages, _ = self.sdk.search.by_key_prefix(
                        f'#message#{conversation_id}#', user=True)
                except Exception as e:
                    # Fetching message bodies after a WS signal can fail too. If we've
                    # already yielded messages this stream, surface it as a MarcusError
                    # (caller must not silently replay via polling); otherwise treat it
                    # like a connect/subscribe failure so the caller can fall back.
                    if yielded:
                        raise MarcusError(f'Lost connection while waiting for Marcus: {e}')
                    raise _WSUnavailable(str(e))
                new = sorted((m for m in messages if isinstance(m, dict) and m.get('key', '') > last_key),
                             key=lambda x: x.get('key', ''))
                for msg in new:
                    last_key = msg.get('key', '')
                    yielded = True
                    yield msg
                    if msg.get('role', '') == 'chariot':
                        return
            raise MarcusError('Timed out waiting for response')
        finally:
            try:
                conn.close()
            except Exception:
                pass

    def _stream_messages(self, conversation_id, after_key=''):
        """Yield conversation messages via WebSocket if configured, else polling.
        Falls back to polling if the WS connection/subscribe fails before any
        message is yielded. If the WS drops after yielding, re-raise as
        MarcusError to avoid silently replaying messages via polling."""
        if self.sdk.keychain.websocket_url():
            yielded = False
            try:
                for msg in self._ws_messages(conversation_id, after_key=after_key):
                    yielded = True
                    yield msg
                return
            except _WSUnavailable:
                if yielded:
                    raise MarcusError('WebSocket connection lost mid-stream')
                # else fall through to polling
        yield from self._poll_messages(conversation_id, after_key=after_key)

    def _parse_tool_name(self, content: str, msg: dict = None) -> str:
        """Extract a human-readable tool name from a tool call message."""
        # Try explicit name fields first
        if msg:
            msg_name = msg.get('name', '')
            if msg_name and msg_name not in ('user', 'chariot', 'tool call', 'tool response'):
                return msg_name
            tool_content = msg.get('toolUseContent', '')
        else:
            tool_content = ''

        # Try parsing JSON content for structured tool calls
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

    def _infer_tool_from_response(self, content: str) -> str:
        """Infer what tool was called based on the response content."""
        try:
            data = json.loads(content) if isinstance(content, str) else content
            if isinstance(data, dict):
                if 'instructions' in data:
                    return 'schema_lookup'
                for key in ('assets', 'risks', 'seeds', 'jobs', 'preseeds'):
                    if key in data:
                        return f'search_{key}'
                if 'status' in data:
                    return 'status_check'
            elif isinstance(data, list) and data:
                first = data[0]
                if isinstance(first, dict):
                    if 'dns' in first or 'source' in first:
                        return 'search_assets'
                    if 'status' in first and 'finding' in str(first):
                        return 'search_risks'
        except (json.JSONDecodeError, TypeError, AttributeError):
            pass
        return ''

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

    def _print_verbose_tool_call(self, content: str, msg: dict):
        """Print expanded tool call details in verbose mode."""
        # Show all message fields except common ones
        extra_keys = {k: v for k, v in msg.items() if k not in ('key', 'role', 'content', 'source') and v}
        if extra_keys:
            self.console.print(f'    [dim]msg fields: {json.dumps(extra_keys, default=str)[:200]}[/dim]')
        # Show the tool call content (input/arguments)
        try:
            data = json.loads(content) if isinstance(content, str) else content
            formatted = json.dumps(data, indent=2, default=str)
            # Truncate to avoid flooding the terminal
            if len(formatted) > 500:
                formatted = formatted[:500] + '\n    ...'
            for line in formatted.split('\n'):
                self.console.print(f'    [dim]{line}[/dim]')
        except (json.JSONDecodeError, TypeError):
            if content:
                self.console.print(f'    [dim]{content[:300]}[/dim]')

    def _print_verbose_tool_response(self, content: str):
        """Print expanded tool response details in verbose mode."""
        try:
            data = json.loads(content) if isinstance(content, str) else content
            formatted = json.dumps(data, indent=2, default=str)
            if len(formatted) > 800:
                formatted = formatted[:800] + '\n    ...'
            for line in formatted.split('\n'):
                self.console.print(f'    [dim]{line}[/dim]')
        except (json.JSONDecodeError, TypeError):
            if content:
                self.console.print(f'    [dim]{content[:400]}[/dim]')

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
            panel_title = f'Marcus @ {self.context.account}' if self.context.account else 'Marcus'
            self.console.print(Panel(Markdown(response), title=panel_title, border_style=self.colors['primary']))

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
            panel_title = f'Marcus @ {self.context.account} -- Ingestion Complete' if self.context.account else 'Marcus -- Ingestion Complete'
            self.console.print(Panel(Markdown(response), title=panel_title, border_style=self.colors['primary']))

    def _marcus_do(self, args):
        """Give Marcus a direct instruction to execute."""
        if not args:
            self.console.print('[dim]Usage: marcus do "<instruction>" [--skill <path>][/dim]')
            self.console.print('[dim]  Examples:[/dim]')
            self.console.print('[dim]    marcus do "add example.com as a seed and start discovery"[/dim]')
            self.console.print('[dim]    marcus do "find SQLi" --skill ./skills/sqli.md[/dim]')
            return

        # Parse --skill flags from args
        remaining = []
        i = 0
        while i < len(args):
            if args[i] == '--skill' and i + 1 < len(args):
                try:
                    name = self.context.load_skill(args[i + 1])
                    self.console.print(f'[dim]Loaded skill: {name}[/dim]')
                except (FileNotFoundError, ValueError) as e:
                    self.console.print(f'[error]{e}[/error]')
                    return
                i += 2
            else:
                remaining.append(args[i])
                i += 1

        instruction = ' '.join(remaining)
        message = self.context.apply_scope_to_message(instruction)
        response = self._send_to_marcus(message)
        if response:
            panel_title = f'Marcus @ {self.context.account}' if self.context.account else 'Marcus'
            self.console.print(Panel(Markdown(response), title=panel_title, border_style=self.colors['primary']))

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
        """Manage Hannibal persistent hunting agents."""
        if not args:
            self.console.print('[bold]Hannibal Hunt Management[/bold]')
            self.console.print('[dim]  hunt start "<prompt>"     Start a new hunt[/dim]')
            self.console.print('[dim]  hunt list                List all hunts[/dim]')
            self.console.print('[dim]  hunt show <uuid>         Show hunt details[/dim]')
            self.console.print('[dim]  hunt pause <uuid>        Pause a hunt[/dim]')
            self.console.print('[dim]  hunt resume <uuid>       Resume a hunt[/dim]')
            self.console.print('[dim]  hunt stop <uuid>         Stop a hunt[/dim]')
            self.console.print('[dim]  hunt interactive [uuid]  Open interactive TUI[/dim]')
            return

        subcmd = args[0].lower()
        rest = args[1:]

        if subcmd == 'start':
            if not rest:
                self.console.print('[error]Usage: hunt start "<prompt>" [--duration 24h] [--scope #asset#...][/error]')
                return

            # Pull --duration/--scope flags out of rest before treating the
            # remainder as the hunt mandate (prompt) text.
            prompt_parts = []
            duration = '24h'
            scope = []
            i = 0
            while i < len(rest):
                token = rest[i]
                if token == '--duration' and i + 1 < len(rest):
                    duration = rest[i + 1]
                    i += 2
                elif token == '--scope' and i + 1 < len(rest):
                    scope.append(rest[i + 1])
                    i += 2
                else:
                    prompt_parts.append(token)
                    i += 1

            prompt = ' '.join(prompt_parts)
            if not prompt:
                self.console.print('[error]Usage: hunt start "<prompt>" [--duration 24h] [--scope #asset#...][/error]')
                return

            from datetime import datetime, timezone, timedelta
            duration_str = duration.strip().lower()
            try:
                if duration_str.endswith('h'):
                    hours = int(duration_str[:-1])
                elif duration_str.endswith('d'):
                    hours = int(duration_str[:-1]) * 24
                else:
                    hours = int(duration_str)
            except ValueError:
                self.console.print(f'[error]Invalid duration: {duration}[/error]')
                return

            if hours <= 0:
                self.console.print('[error]Duration must be positive[/error]')
                return
            if hours > 72:
                self.console.print('[error]Maximum hunt duration is 72 hours.[/error]')
                return

            expires_at = (datetime.now(timezone.utc) + timedelta(hours=hours)).strftime('%Y-%m-%dT%H:%M:%SZ')
            body = {'prompt': prompt, 'expiresAt': expires_at}
            if scope:
                body['scope'] = scope

            with self.console.status('Launching hunt...', spinner='dots', spinner_style=self.colors['primary']):
                result = self.sdk.post('hunt', body)
            uuid = result.get('uuid', '?')
            status = result.get('status', '?')
            self.console.print('[bold red]Hannibal is at the gates![/bold red]')
            self.console.print(f'  Hunt:   {uuid}')
            self.console.print(f'  Status: [green]{status}[/green]')
            self.console.print(f'  Track:  hunt show {uuid}')
        elif subcmd == 'list':
            with self.console.status('Loading hunts...', spinner='dots', spinner_style=self.colors['primary']):
                resp = self.sdk.my({'key': '#hunt'}, pages=100)
            hunts = self._extract_console_hunts(resp)
            if not hunts:
                self.console.print('[dim]No hunts found.[/dim]')
                return
            self.console.print(f'[bold]{len(hunts)} hunt(s)[/bold]')
            for h in hunts:
                uuid = h.get('uuid', '?')
                status = h.get('status', '?')
                prompt = (h.get('prompt', '') or '')[:50]
                iters = h.get('iterationCount', 0)
                finds = h.get('findingsCount', 0)
                self.console.print(f'  {uuid[:12]}...  [{self._hunt_color(status)}]{status}[/]  i={iters} f={finds}  {prompt}')
        elif subcmd == 'show':
            if not rest:
                self.console.print('Usage: hunt show <uuid>')
            else:
                uuid = rest[0]
                with self.console.status('Loading...', spinner='dots', spinner_style=self.colors['primary']):
                    resp = self.sdk.my({'key': f'#hunt#{uuid}'})
                hunts = self._extract_console_hunts(resp)
                if not hunts:
                    self.console.print(f'[error]Hunt {uuid} not found.[/error]')
                    return
                h = hunts[0]
                self.console.print(f'[bold]Hunt {h.get("uuid", "?")}[/bold]')
                self.console.print(f'  Status:     [{self._hunt_color(h.get("status", ""))}]{h.get("status", "?")}[/]')
                self.console.print(f'  Created:    {h.get("created", "?")}')
                self.console.print(f'  Expires:    {h.get("expiresAt", "?")}')
                self.console.print(f'  Iterations: {h.get("iterationCount", 0)}')
                self.console.print(f'  Findings:   {h.get("findingsCount", 0)}')
                self.console.print(f'  Mandate:    {h.get("prompt", "")}')
        elif subcmd == 'pause':
            if not rest:
                self.console.print('Usage: hunt pause <uuid>')
            else:
                with self.console.status('Pausing...', spinner='dots', spinner_style=self.colors['primary']):
                    result = self.sdk.put(f'hunt/{rest[0]}', {'status': 'paused'})
                self.console.print(f'Hunt {rest[0]}: [yellow]paused[/yellow]')
        elif subcmd == 'resume':
            if not rest:
                self.console.print('Usage: hunt resume <uuid>')
            else:
                with self.console.status('Resuming...', spinner='dots', spinner_style=self.colors['primary']):
                    result = self.sdk.put(f'hunt/{rest[0]}', {'status': 'active'})
                self.console.print(f'Hunt {rest[0]}: [green]active[/green]')
        elif subcmd == 'stop':
            if not rest:
                self.console.print('Usage: hunt stop <uuid>')
            else:
                with self.console.status('Stopping...', spinner='dots', spinner_style=self.colors['primary']):
                    result = self.sdk.put(f'hunt/{rest[0]}', {'status': 'stopped'})
                self.console.print(f'Hunt {rest[0]}: [red]stopped[/red]')
        elif subcmd == 'interactive':
            from praetorian_cli.ui.hunt.app import run_hunt_tui
            uuid = rest[0] if rest else None
            run_hunt_tui(self.sdk, hunt_uuid=uuid)
        else:
            self.console.print(f'[error]Unknown hunt subcommand: {subcmd}. Type "hunt" for help.[/error]')

    @staticmethod
    def _extract_console_hunts(resp):
        if isinstance(resp, list):
            return resp
        for key in ('hunts', 'data'):
            if key in resp and isinstance(resp[key], list):
                return resp[key]
        for key in resp:
            if isinstance(resp[key], list):
                return resp[key]
        return []

    @staticmethod
    def _hunt_color(status):
        return {'active': 'green', 'paused': 'yellow', 'completed': 'cyan',
                'stopped': 'red', 'expired': 'magenta', 'errored': 'red'}.get(status, 'white')
