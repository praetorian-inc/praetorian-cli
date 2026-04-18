"""Security tools commands: run/status/download/install/capabilities/scan/tag. Mixed into GuardConsole."""

import json
import os
import time

from rich.markdown import Markdown
from rich.markup import escape
from rich.panel import Panel
from rich.table import Table
from rich.text import Text


class ToolCommands:
    """Security tool and operation console commands. Mixed into GuardConsole."""

    def _cmd_scan(self, args):
        if not args:
            self.console.print('[dim]Usage: scan <asset_key> [capability][/dim]')
            return
        asset_key = args[0]
        capabilities = args[1:] if len(args) > 1 else []
        try:
            result = self.sdk.jobs.add(asset_key, capabilities=capabilities)
            self.console.print(f'[success]Job queued[/success]')
            self.console.print_json(json.dumps(result, indent=2))
        except Exception as e:
            self.console.print(f'[error]{e}[/error]')

    def _cmd_tag(self, args):
        if len(args) < 2:
            self.console.print('[dim]Usage: tag <risk_key> <tag1> [tag2 ...][/dim]')
            return
        key = args[0]
        tags = args[1:]
        try:
            self.sdk.risks.update(key, tags=tags)
            self.console.print(f'[success]Tagged {key} with: {", ".join(tags)}[/success]')
        except Exception as e:
            self.console.print(f'[error]{e}[/error]')

    def _cmd_run(self, args):
        """Run a named security tool against a target, or execute active tool."""
        from praetorian_cli.handlers.run import TOOL_ALIASES
        from praetorian_cli.runners.local import is_installed as _is_installed

        if not args and self.context.active_tool:
            self._cmd_execute([])
            return
        if not args:
            self._print_tool_catalog(TOOL_ALIASES)
            return

        tool_name = args[0].lower()
        alias = TOOL_ALIASES.get(tool_name)
        if not alias:
            available = ', '.join(sorted(k for k in TOOL_ALIASES if k != 'secrets'))
            self.console.print(f'[error]Unknown tool: {tool_name}. Available: {available}[/error]')
            return

        rest = args[1:]

        # `run <tool> --help` — forward to local binary if installed.
        if rest and rest[0] == '--help':
            self._print_tool_help(tool_name)
            return

        if not rest:
            self.console.print(f'[dim]Usage: {tool_name} <target_key> [--ask] [--wait] [-- <tool-args>...][/dim]')
            self.console.print(f'[dim]  Target type: {alias["target_type"]}[/dim]')
            self.console.print(f'[dim]  {alias["description"]}[/dim]')
            return

        raw_target = rest[0]
        remaining = rest[1:]

        # Split own flags from passthrough. Honor `--` as an explicit boundary:
        # everything after `--` is passthrough, even if it collides with `--wait`/`--ask`.
        OWN_FLAGS = {'--ask', '--wait'}
        pass_through = []
        own = []
        if '--' in remaining:
            idx = remaining.index('--')
            own = remaining[:idx]
            pass_through = remaining[idx + 1:]
        else:
            for a in remaining:
                if a in OWN_FLAGS:
                    own.append(a)
                else:
                    pass_through.append(a)

        use_agent = '--ask' in own
        wait = '--wait' in own

        if pass_through and use_agent:
            self.console.print(
                '[error]Extra arguments are not supported with --ask (agent path). '
                'Drop --ask or use structured config.[/error]'
            )
            return

        if pass_through:
            if not _is_installed(tool_name):
                self.console.print(
                    f'[error]Extra arguments require the {tool_name} binary to be installed locally. '
                    f'Run "install {tool_name}" first.[/error]'
                )
                return
            self._run_tool_locally(tool_name, raw_target, pass_through)
            return

        # No passthrough — existing remote/agent flow.
        from praetorian_cli.handlers.run import resolve_target
        target_key, warning = resolve_target(self.sdk, raw_target, alias['target_type'])
        if not target_key:
            self.console.print(f'[error]{warning}[/error]')
            return
        if warning:
            self.console.print(f'[warning]{warning}[/warning]')

        capability = alias.get('capability')
        config = dict(alias.get('default_config', {}))

        if alias.get('agent') and (use_agent or not capability):
            agent_name = alias['agent']
            task_desc = f'Run {capability} against {target_key} and analyze the results.' if capability else f'Analyze {target_key} thoroughly.'
            message = self.context.apply_scope_to_message(task_desc)
            self.console.print(f'[info]Delegating to {agent_name} via Marcus...[/info]')
            response_text = self._send_to_marcus(message)
            if response_text:
                from rich.markdown import Markdown
                self.console.print(Markdown(response_text))
        else:
            import json
            config_str = json.dumps(config) if config else None
            result = self._try_queue_job(target_key, capability, config_str)
            if result is None:
                return
            if wait:
                self._wait_for_job(target_key, capability)

    def _print_tool_catalog(self, TOOL_ALIASES):
        """Render the agents/capabilities catalog shown when `run` is called bare."""
        agents = {k: v for k, v in TOOL_ALIASES.items() if v.get('agent') and k != 'secrets'}
        table = Table(title='Agents', border_style=self.colors['primary'])
        table.add_column('Agent', style=f'bold {self.colors["primary"]}', min_width=16)
        table.add_column('Description')
        for name, info in sorted(agents.items()):
            table.add_row(name, info['description'])
        self.console.print(table)

        caps = {k: v for k, v in TOOL_ALIASES.items() if not v.get('agent') and k != 'secrets'}
        if caps:
            table2 = Table(title='Capabilities', border_style=self.colors['dim'])
            table2.add_column('Capability', style=f'bold {self.colors["primary"]}', min_width=16)
            table2.add_column('Target', style=self.colors['accent'])
            table2.add_column('Description')
            for name, info in sorted(caps.items()):
                table2.add_row(name, info['target_type'], info['description'])
            self.console.print(table2)

        self.console.print(f'\n[dim]Usage: use <name> or <name> <target_key>[/dim]')

    def _print_tool_help(self, tool_name):
        """Run `<tool> --help` locally and stream its output to the console."""
        from praetorian_cli.runners.local import is_installed as _is_installed, LocalRunner
        if not _is_installed(tool_name):
            self.console.print(
                f'[warning]{tool_name} is not installed locally. Run "install {tool_name}" first.[/warning]'
            )
            return
        try:
            runner = LocalRunner(tool_name)
            proc = runner.run_streaming(['--help'])
            for line in proc.stdout:
                self.console.print(line.rstrip('\n'), markup=False, highlight=False)
            stderr = proc.stderr.read() if proc.stderr else ''
            if stderr:
                self.console.print(f'[dim]{escape(stderr)}[/dim]')
        except Exception as e:
            self.console.print(f'[error]{e}[/error]')

    def _run_tool_locally(self, tool_name, raw_target, pass_through):
        """Run an installed tool binary locally from the console."""
        from praetorian_cli.runners.local import LocalRunner, get_tool_plugin

        # Strip Guard key prefix for the raw target (same logic as CLI _run_local).
        target = raw_target
        if raw_target.startswith('#'):
            parts = raw_target.split('#')
            target = parts[-1] if len(parts) > 3 else parts[2] if len(parts) > 2 else raw_target

        plugin = get_tool_plugin(tool_name)
        tool_argv = plugin.build_args(target, pass_through=list(pass_through or []))

        try:
            runner = LocalRunner(tool_name)
        except FileNotFoundError as e:
            self.console.print(f'[error]{e}[/error]')
            return

        self.console.print(f'[info]Running {tool_name} locally against {target}...[/info]')
        self.console.print(f'[dim]Command: {tool_name} {" ".join(tool_argv)}[/dim]')
        self.console.print('[dim]' + '─' * 60 + '[/dim]')

        import subprocess
        proc = runner.run_streaming(tool_argv)
        output_lines = []
        try:
            for line in proc.stdout:
                self.console.print(line.rstrip('\n'), markup=False, highlight=False)
                output_lines.append(line)
            proc.wait(timeout=600)
        except subprocess.TimeoutExpired:
            proc.kill()
            try:
                proc.wait(timeout=5)
            except Exception:
                pass
            self.console.print('[error]Timed out (10 min).[/error]')

        stderr = proc.stderr.read() if proc.stderr else ''
        if stderr:
            self.console.print(f'[dim]{escape(stderr)}[/dim]')

        self.console.print('[dim]' + '─' * 60 + '[/dim]')
        self.console.print(f'[dim]Exit code: {proc.returncode}[/dim]')

        # Best-effort upload to Guard (mirrors CLI behavior).
        output_text = ''.join(output_lines)
        if output_text.strip():
            try:
                import tempfile, os
                with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False, prefix=f'{tool_name}-') as f:
                    f.write(output_text)
                    tmp_path = f.name
                guard_path = f'proofs/local/{tool_name}/{target.replace("/", "_")}'
                self.sdk.files.add(tmp_path, guard_path)
                os.unlink(tmp_path)
                self.console.print(f'[success]Output uploaded to Guard: {guard_path}[/success]')
            except Exception as e:
                self.console.print(f'[warning]Failed to upload output: {e}[/warning]')

    def _try_queue_job(self, target_key, capability, config_str):
        """Try to queue a job. If frozen/blocked, fallback to the login user's own account."""
        # First attempt
        first_error = None
        try:
            result = self.sdk.jobs.add(target_key, [capability], config_str)
        except Exception as e:
            first_error = e

        if first_error is None:
            # Success on first try
            pass
        else:
            error_msg = str(first_error).lower()
            is_frozen = 'frozen' in error_msg or 'blocked' in error_msg

            if not is_frozen:
                self.console.print(f'[error]{first_error}[/error]')
                return None

            # Frozen/blocked -- fallback by clearing impersonation
            login_user = None
            try:
                login_user = self.sdk.accounts.login_principal()
            except Exception:
                pass
            display_user = login_user or 'API key owner'

            self.console.print(f'[dim]Account frozen -- retrying as {display_user}[/dim]')
            saved = self.sdk.keychain.account
            self.sdk.keychain.account = None
            try:
                result = self.sdk.jobs.add(target_key, [capability], config_str)
            except Exception as e2:
                self.console.print(f'[error]Fallback also failed: {e2}[/error]')
                return None
            finally:
                self.sdk.keychain.account = saved

        job_key = ''
        if isinstance(result, list) and result:
            job_key = result[0].get('key', '')
        elif isinstance(result, dict):
            job_key = result.get('key', '')
        self.context._last_job_key = job_key
        self.console.print(f'[success]Job queued: {capability} -> {target_key}[/success]')
        self.console.print(f'[dim]Job key: {job_key}[/dim]')
        self.console.print(f'[dim]Use "status" to check progress, or "run --wait" to wait for results.[/dim]')
        return result

    def _wait_for_job(self, target_key, capability):
        """Poll for job completion and show results."""
        max_wait = 300
        start_time = time.time()
        with self.console.status('Waiting for job...', spinner='dots', spinner_style=self.colors['primary']) as status:
            while time.time() - start_time < max_wait:
                try:
                    jobs, _ = self.sdk.jobs.list(target_key.lstrip('#'))
                    matching = [j for j in jobs if capability in j.get('source', '') or capability in j.get('key', '')]
                    if matching:
                        latest = sorted(matching, key=lambda j: j.get('created', 0), reverse=True)[0]
                        st = latest.get('status', '')
                        if st.startswith('JP'):
                            elapsed = int(time.time() - start_time)
                            self.console.print(f'\n[success]Job completed in {elapsed}s[/success]')
                            self._render_job_results(latest, capability)
                            return
                        elif st.startswith('JF'):
                            self.console.print(f'\n[error]Job failed.[/error]')
                            self._render_job_results(latest, capability)
                            return
                        else:
                            elapsed = int(time.time() - start_time)
                            status.update(f'{capability} running ({elapsed}s)...')
                except Exception:
                    pass
                time.sleep(5)
        self.console.print('[warning]Timed out waiting for job (5 min).[/warning]')

    def _cmd_status(self, args):
        """Check status of last job or a specific job key."""
        job_key = ''
        if args:
            job_key = args[0]
        elif hasattr(self.context, '_last_job_key') and self.context._last_job_key:
            job_key = self.context._last_job_key
        else:
            self.console.print('[dim]No recent job. Usage: status <job_key>[/dim]')
            self.console.print('[dim]Or run a tool first, then "status" to check it.[/dim]')
            return

        try:
            job = self.sdk.jobs.get(job_key)
            if not job:
                self.console.print(f'[dim]Job not found: {job_key}[/dim]')
                return

            status_raw = job.get('status', '')
            status_code = status_raw[:2]
            status_map = {
                'JQ': ('QUEUED', self.colors['info']),
                'JR': ('RUNNING', self.colors['accent']),
                'JP': ('PASSED', self.colors['success']),
                'JF': ('FAILED', self.colors['error']),
            }
            status_label, color = status_map.get(status_code, (status_code, self.colors['dim']))

            source = job.get('source', '')
            cap = source.split('#')[0] if '#' in source else source
            dns = job.get('dns', '')
            created = job.get('created', '')
            started = job.get('started', '') or '—'
            finished = job.get('finished', '') or '—'

            status_text = Text()
            status_text.append(f'{cap}', style=f'bold {self.colors["primary"]}')
            status_text.append(f' -> {dns}\n', style='white')
            status_text.append(f'Status: ', style=self.colors['dim'])
            status_text.append(f'{status_label}\n', style=f'bold {color}')
            status_text.append(f'Created:  {created}\n', style=self.colors['dim'])
            status_text.append(f'Started:  {started}\n', style=self.colors['dim'])
            status_text.append(f'Finished: {finished}', style=self.colors['dim'])

            self.console.print(Panel(status_text, title='Job Status', border_style=color))

            # Show full results for completed/failed jobs
            if status_code in ('JP', 'JF'):
                self._render_job_results(job, cap)

        except Exception as e:
            self.console.print(f'[error]{e}[/error]')

    def _cmd_download(self, args):
        """Download job outputs, proofs, and files to a local directory."""
        # Parse arguments
        target = args[0] if args else 'all'
        output_dir = None
        for i, a in enumerate(args):
            if a in ('--output', '-o') and i + 1 < len(args):
                output_dir = args[i + 1]

        # Build output directory
        account_name = self.context.account or 'default'
        # Clean account name for filesystem
        safe_name = account_name.replace('@', '_at_').replace('+', '_')
        for c in '<>:"/\\|?*':
            safe_name = safe_name.replace(c, '_')

        if not output_dir:
            output_dir = os.path.join(os.getcwd(), 'guard-output', safe_name)

        os.makedirs(output_dir, exist_ok=True)

        if target == 'all':
            self.console.print(f'[info]Downloading all outputs to {output_dir}/[/info]')
            self._download_category('proofs', output_dir)
            self._download_category('agents', output_dir)
            self._download_category('definitions', output_dir)
        elif target == 'proofs':
            self.console.print(f'[info]Downloading proofs to {output_dir}/[/info]')
            self._download_category('proofs', output_dir)
        elif target == 'agents':
            self.console.print(f'[info]Downloading agent outputs to {output_dir}/[/info]')
            self._download_category('agents', output_dir)
        elif target == 'definitions':
            self.console.print(f'[info]Downloading definitions to {output_dir}/[/info]')
            self._download_category('definitions', output_dir)
        elif target == 'files':
            self.console.print(f'[info]Downloading all files to {output_dir}/[/info]')
            self._download_category('', output_dir)
        else:
            # Treat as a file path prefix to download
            self.console.print(f'[info]Downloading {target} to {output_dir}/[/info]')
            self._download_category(target, output_dir)

        self.console.print(f'[success]Downloads saved to {output_dir}/[/success]')

    def _download_category(self, prefix: str, output_dir: str):
        """Download all files matching a prefix to local directory."""
        try:
            files, _ = self.sdk.files.list(prefix, pages=10)
        except Exception as e:
            self.console.print(f'[error]Failed to list files: {e}[/error]')
            return

        if not files:
            self.console.print(f'[dim]No files found for: {prefix or "all"}[/dim]')
            return

        self.console.print(f'[dim]Found {len(files)} files...[/dim]')
        downloaded = 0
        errors = 0

        for f in files:
            file_key = f.get('key', '')
            # Extract the path from #file#<path>
            if file_key.startswith('#file#'):
                file_path = file_key[6:]  # strip #file#
            else:
                file_path = f.get('name', file_key)

            if not file_path or file_path.startswith('#'):
                continue

            # Build local path
            local_path = os.path.join(output_dir, file_path)
            local_dir = os.path.dirname(local_path)

            try:
                os.makedirs(local_dir, exist_ok=True)
                content = self.sdk.files.get(file_path)
                with open(local_path, 'wb') as fp:
                    fp.write(content)
                downloaded += 1
            except Exception:
                errors += 1

        self.console.print(f'[dim]  Downloaded: {downloaded}, Errors: {errors}[/dim]')

    def _cmd_install(self, args):
        """Install a capability binary locally from GitHub."""
        from praetorian_cli.runners.local import install_tool, INSTALLABLE_TOOLS, is_installed
        if not args:
            self.console.print('[dim]Usage: install <tool_name|all>[/dim]')
            self.console.print(f'[dim]Available: {", ".join(sorted(INSTALLABLE_TOOLS))}[/dim]')
            return
        tool_name = args[0].lower()
        force = '--force' in args
        if tool_name == 'all':
            for name in sorted(INSTALLABLE_TOOLS):
                try:
                    if not force and is_installed(name):
                        self.console.print(f'  {name}: [dim]already installed[/dim]')
                    else:
                        with self.console.status(f'Installing {name}...', spinner='dots', spinner_style=self.colors['primary']):
                            path = install_tool(name, force=force)
                        self.console.print(f'  {name}: [success]{path}[/success]')
                except Exception as e:
                    self.console.print(f'  {name}: [error]{e}[/error]')
        else:
            try:
                with self.console.status(f'Installing {tool_name}...', spinner='dots', spinner_style=self.colors['primary']):
                    path = install_tool(tool_name, force=force)
                self.console.print(f'[success]Installed: {path}[/success]')
            except Exception as e:
                self.console.print(f'[error]{e}[/error]')

    def _cmd_installed(self, args):
        """List locally installed capability binaries."""
        from praetorian_cli.runners.local import list_installed, INSTALLABLE_TOOLS
        inst = list_installed()
        table = Table(title='Local Binaries', border_style=self.colors['primary'])
        table.add_column('Tool', style=f'bold {self.colors["primary"]}', min_width=16)
        table.add_column('Status', min_width=10)
        table.add_column('Path', style=self.colors['dim'])
        for name in sorted(INSTALLABLE_TOOLS):
            if name in inst:
                table.add_row(name, f'[success]installed[/success]', inst[name])
            else:
                table.add_row(name, f'[dim]---[/dim]', '')
        self.console.print(table)

    def _cmd_capabilities(self, args):
        """List available capabilities from the backend. Numbered for 'use <#>'."""
        name_filter = args[0] if args else ''
        try:
            result = self.sdk.capabilities.list(name=name_filter)
            if isinstance(result, list):
                caps = result
            elif isinstance(result, dict):
                caps = result.get('capabilities', result.get('data', []))
            elif isinstance(result, tuple):
                caps = result[0] if result[0] else []
            else:
                caps = []

            if isinstance(caps, list) and caps:
                table = Table(title=f'Capabilities ({len(caps)})', border_style=self.colors['primary'])
                table.add_column('#', style=self.colors['dim'], width=4)
                table.add_column('Name', style=f'bold {self.colors["primary"]}')
                table.add_column('Target', style=self.colors['accent'])
                table.add_column('Executor', style=self.colors['dim'])
                table.add_column('Description')

                self._capability_list = []
                for i, cap in enumerate(caps, 1):
                    if isinstance(cap, dict):
                        name = str(cap.get('name', cap.get('Name', '')))
                        target = cap.get('target', cap.get('Target', ''))
                        if isinstance(target, list):
                            target = ','.join(target)
                        desc = str(cap.get('description', cap.get('Description', '')))[:50]
                        executor = str(cap.get('executor', ''))
                        table.add_row(str(i), name, str(target), executor, desc)
                        self._capability_list.append(name)
                self.console.print(table)
                self.console.print(f'\n[dim]Use "use <#>" or "use <name>" to select a capability.[/dim]')
            else:
                self.console.print('[dim]No capabilities found.[/dim]')
        except Exception as e:
            self.console.print(f'[error]{e}[/error]')
