"""Search commands: search/find/assets/risks/jobs/info. Mixed into GuardConsole."""

import json

from rich.table import Table


class SearchCommands:
    """Search-related console commands. Mixed into GuardConsole."""

    def _cmd_search(self, args):
        if not args:
            self.console.print('[dim]Usage: search <term> [--kind <type>][/dim]')
            return

        # Parse args
        raw_args = list(args)
        kind = None
        if '--kind' in raw_args:
            idx = raw_args.index('--kind')
            if idx + 1 < len(raw_args):
                kind = raw_args[idx + 1]
                raw_args = raw_args[:idx] + raw_args[idx + 2:]
        term = ' '.join(raw_args)

        # Context-smart: if we have paged results, filter them locally first
        if self._paged_results and not kind:
            filtered = [
                r for r in self._paged_results
                if term.lower() in (r.get('key', '') + ' ' + r.get('name', '') + ' ' + r.get('dns', '') + ' ' + r.get('title', '')).lower()
            ]
            if filtered:
                self._render_results(filtered, f'Search: "{term}" in {self._paged_title}')
                return

        # Fall through to API search
        try:
            results, offset = self.sdk.search.by_term(term, kind)
            self._render_results(results, f'Search: {term}')
        except Exception as e:
            self.console.print(f'[error]Search failed: {e}[/error]')

    def _cmd_find(self, args):
        if not args:
            self.console.print('[dim]Usage: find <term> [--type <type>] [--limit <n>][/dim]')
            return

        # Parse args
        term = []
        kind = None
        limit = 200
        i = 0
        while i < len(args):
            if args[i] == '--type' and i + 1 < len(args):
                kind = args[i + 1]
                i += 2
            elif args[i] == '--limit' and i + 1 < len(args):
                limit = int(args[i + 1])
                i += 2
            else:
                term.append(args[i])
                i += 1
        term = ' '.join(term)

        try:
            all_results, _ = self.sdk.search.fulltext(term, kind=kind, limit=limit)
        except ValueError as e:
            self.console.print(f'[error]{e}[/error]')
            return

        if not kind and all_results:
            # Cross-type display: group by entity type and show type labels
            self._render_typed_results(all_results, f'Find: {term}')
        else:
            self._render_results(all_results, f'Find: {term}')

        if len(all_results) >= limit:
            self.console.print(f'[dim]Showing {limit} results. Use --limit to increase.[/dim]')

    def _cmd_assets(self, args):
        try:
            filter_text = ' '.join(args) if args else (self.context.scope or '')
            results, _ = self.sdk.assets.list(filter_text, pages=1)
            title = f'Assets: {filter_text}' if filter_text else 'Assets'
            self._render_results(results, title)
        except Exception as e:
            self.console.print(f'[error]{e}[/error]')

    def _cmd_risks(self, args):
        try:
            filter_text = ' '.join(args) if args else (self.context.scope or '')
            results, _ = self.sdk.risks.list(filter_text, pages=1)
            title = f'Risks: {filter_text}' if filter_text else 'Risks'
            self._render_results(results, title)
        except Exception as e:
            self.console.print(f'[error]{e}[/error]')

    def _cmd_jobs(self, args):
        """List jobs, optionally filtered. Also supports 'jobs <key>' to check a specific job."""
        filter_term = ' '.join(args) if args else ''
        try:
            results, _ = self.sdk.jobs.list(filter_term, pages=1)
            if not results:
                self.console.print('[dim]No jobs found.[/dim]')
                return

            table = Table(title=f'Jobs ({len(results)} results)', border_style=self.colors['primary'])
            table.add_column('#', style=self.colors['dim'], width=4)
            table.add_column('Capability', style=f'bold {self.colors["primary"]}')
            table.add_column('Target', style='white')
            table.add_column('Status', min_width=8)
            table.add_column('Created', style=self.colors['dim'])

            for i, job in enumerate(results[:50], 1):
                key = job.get('key', '')
                source = job.get('source', '')
                cap = source.split('#')[0] if '#' in source else source
                dns = job.get('dns', '')
                status_raw = job.get('status', '')
                status_code = status_raw[:2] if status_raw else '?'
                created = job.get('created', '')[:16]

                # Color status
                status_map = {
                    'JQ': (f'[info]QUEUED[/info]'),
                    'JR': (f'[accent]RUNNING[/accent]'),
                    'JP': (f'[success]PASSED[/success]'),
                    'JF': (f'[error]FAILED[/error]'),
                }
                status_display = status_map.get(status_code, status_code)
                table.add_row(str(i), cap, dns, status_display, created)

            self.console.print(table)
        except Exception as e:
            self.console.print(f'[error]{e}[/error]')

    def _cmd_info(self, args):
        if not args:
            self.console.print('[dim]Usage: info <key>[/dim]')
            return
        key = args[0]
        try:
            if '#risk#' in key:
                result = self.sdk.risks.get(key, details=True)
            elif '#asset#' in key:
                result = self.sdk.assets.get(key, details=True)
            else:
                result = self.sdk.search.by_exact_key(key, get_attributes=True)
            self.console.print_json(json.dumps(result, indent=2))
        except Exception as e:
            self.console.print(f'[error]{e}[/error]')
