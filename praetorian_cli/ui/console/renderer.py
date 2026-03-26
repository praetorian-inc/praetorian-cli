"""Rendering helpers for the Guard console. Mixed into GuardConsole."""

from rich.markdown import Markdown
from rich.panel import Panel
from rich.table import Table
from rich.text import Text


class RendererMixin:
    """Rendering helpers for console output. Mixed into GuardConsole."""

    def _render_results(self, results: list, title: str):
        if not results:
            self.console.print(f'[dim]No results for: {title}[/dim]')
            if self.context.scope:
                self.console.print(f'[dim]Current scope: {self.context.scope} -- use "unset scope" to broaden[/dim]')
            return

        table = Table(title=f'{title} ({len(results)} results)', border_style=self.colors['primary'])
        table.add_column('#', style=self.colors['dim'], width=4)
        table.add_column('Key', style=self.colors['primary'])
        table.add_column('Name', style='white')
        table.add_column('Status', style=self.colors['accent'])

        # Update _target_list so "set target <#>" works from any listing
        self._target_list = []
        for i, item in enumerate(results[:100], 1):
            key = item.get('key', '')
            name = item.get('name', item.get('dns', item.get('title', '')))
            status = item.get('status', '')
            table.add_row(str(i), key, str(name), status)
            self._target_list.append(key)

        self.console.print(table)
        if len(results) > 100:
            self.console.print(f'[dim]Showing first 100 of {len(results)} results[/dim]')

    def _render_evidence(self, hydrated: dict):
        risk = hydrated.get('risk', {})
        definition = hydrated.get('definition')
        evidence = hydrated.get('evidence', [])
        affected = hydrated.get('affected_assets', [])

        # Header
        self.console.print(Panel(
            f"[bold]{risk.get('name', 'Unknown')}[/bold]\n"
            f"Status: {risk.get('status', '?')} | Asset: {risk.get('dns', '?')} | Source: {risk.get('source', '?')}",
            title='Risk Detail',
            border_style=self.colors['primary'],
        ))

        # Definition sections
        if definition:
            if definition.get('description'):
                self.console.print(f'\n[section]DESCRIPTION[/section]')
                self.console.print(Markdown(definition['description']))
            if definition.get('impact'):
                self.console.print(f'\n[section]IMPACT[/section]')
                self.console.print(Markdown(definition['impact']))
            if definition.get('recommendation'):
                self.console.print(f'\n[section]RECOMMENDATION[/section]')
                self.console.print(Markdown(definition['recommendation']))

        # Evidence
        if evidence:
            self.console.print(f'\n[section]EVIDENCE ({len(evidence)} sources)[/section]')
            for ev in evidence:
                src = ev.get('source', '?')
                if src == 'attribute':
                    self.console.print(f"  [dim][attribute][/dim] {ev.get('name')}: {ev.get('value')}")
                elif src == 'webpage':
                    self.console.print(f"  [dim][webpage][/dim]   {ev.get('url', '?')}")
                elif src == 'file':
                    self.console.print(f"  [dim][file][/dim]      {ev.get('path', '?')} ({ev.get('size', '?')})")

        # References
        if definition and definition.get('references'):
            self.console.print(f'\n[section]REFERENCES[/section]')
            for ref in definition['references']:
                self.console.print(f'  - {ref}')

        # Affected assets
        if affected:
            self.console.print(f'\n[section]AFFECTED ASSETS ({len(affected)})[/section]')
            for asset in affected[:10]:
                self.console.print(f"  {asset.get('key', '?')}")
            if len(affected) > 10:
                self.console.print(f'  [dim]...and {len(affected) - 10} more[/dim]')

    def _render_entity_detail(self, entity: dict, entity_type: str):
        """Render a rich detail view for an asset or risk."""
        key = entity.get('key', '')
        name = entity.get('name', entity.get('dns', ''))
        status = entity.get('status', '')
        created = entity.get('created', '')

        # Header
        header = Text()
        header.append(f'{name}\n', style=f'bold {self.colors["primary"]}')
        header.append(f'Key: {key}\n', style=self.colors['dim'])
        header.append(f'Status: ', style=self.colors['dim'])
        header.append(f'{status}', style=f'bold {self.colors["accent"]}')
        if created:
            header.append(f'  Created: {created}', style=self.colors['dim'])

        if entity_type == 'Risk':
            priority = entity.get('priority', '')
            severity_map = {0: 'CRITICAL', 10: 'HIGH', 20: 'MEDIUM', 30: 'LOW', 40: 'INFO', 60: 'EXPOSURE'}
            severity = severity_map.get(priority, str(priority))
            header.append(f'\nSeverity: ', style=self.colors['dim'])
            header.append(f'{severity}', style=f'bold {self.colors["error"]}' if priority <= 10 else f'{self.colors["accent"]}')
            title = entity.get('title', '')
            if title:
                header.append(f'\nTitle: {title}', style='white')

        if entity_type == 'Asset':
            cls = entity.get('class', '')
            dns = entity.get('dns', '')
            surface = entity.get('attackSurface', [])
            if cls:
                header.append(f'\nClass: {cls}', style=self.colors['dim'])
            if dns and dns != name:
                header.append(f'  DNS: {dns}', style=self.colors['dim'])
            if surface:
                header.append(f'  Surface: {", ".join(surface)}', style=self.colors['dim'])

        self.console.print(Panel(header, title=entity_type, border_style=self.colors['primary']))

        # Attributes
        attrs = entity.get('attributes', [])
        if attrs:
            table = Table(title=f'Attributes ({len(attrs)})', border_style=self.colors['dim'])
            table.add_column('Name', style=self.colors['primary'])
            table.add_column('Value', style='white')
            for a in attrs[:20]:
                table.add_row(a.get('name', ''), str(a.get('value', '')))
            self.console.print(table)

        # Associated risks (for assets)
        assoc_risks = entity.get('associated_risks', [])
        if assoc_risks:
            table = Table(title=f'Associated Risks ({len(assoc_risks)})', border_style=self.colors['error'])
            table.add_column('Risk', style=self.colors['primary'])
            table.add_column('Status', style=self.colors['accent'])
            for r in assoc_risks[:10]:
                table.add_row(r.get('name', r.get('key', '')), r.get('status', ''))
            self.console.print(table)

        # Affected assets (for risks)
        affected = entity.get('affected_assets', [])
        if affected:
            table = Table(title=f'Affected Assets ({len(affected)})', border_style=self.colors['primary'])
            table.add_column('Asset', style=self.colors['primary'])
            table.add_column('Status', style=self.colors['accent'])
            for a in affected[:10]:
                table.add_row(a.get('key', ''), a.get('status', ''))
            self.console.print(table)

        # History (for risks)
        history = entity.get('history', [])
        if history:
            table = Table(title='History', border_style=self.colors['dim'])
            table.add_column('Date', style=self.colors['dim'])
            table.add_column('By', style='white')
            table.add_column('Change', style=self.colors['accent'])
            for h in history[:10]:
                table.add_row(
                    h.get('updated', ''),
                    h.get('by', ''),
                    f'{h.get("from", "")} -> {h.get("to", "")}',
                )
            self.console.print(table)

    def _render_job_results(self, job: dict, capability: str):
        """Render rich results from a completed job -- findings, assets, ports, attributes."""
        job_key = job.get('key', '')
        dns = job.get('dns', '')
        status_code = job.get('status', '')[:2]

        # Fetch all results produced by this job
        risks = []
        assets = []
        attributes = []
        try:
            risks, _ = self.sdk.search.by_source(job_key, 'risk')
        except Exception:
            pass
        try:
            assets, _ = self.sdk.search.by_source(job_key, 'asset')
        except Exception:
            pass
        try:
            attributes, _ = self.sdk.search.by_source(job_key, 'attribute')
        except Exception:
            pass

        # Build summary
        summary_parts = []
        if risks:
            summary_parts.append(f'{len(risks)} finding(s)')
        if assets:
            summary_parts.append(f'{len(assets)} asset(s) discovered')
        if attributes:
            summary_parts.append(f'{len(attributes)} attribute(s)')
        if not summary_parts:
            summary_parts.append('no new results')

        color = self.colors['success'] if status_code == 'JP' else self.colors['error']
        status_label = 'PASSED' if status_code == 'JP' else 'FAILED'

        header = Text()
        header.append(f'{capability}', style=f'bold {self.colors["primary"]}')
        header.append(f' -> {dns}\n', style='white')
        header.append(f'Status: ', style=self.colors['dim'])
        header.append(f'{status_label}', style=f'bold {color}')
        header.append(f' -- {", ".join(summary_parts)}', style=self.colors['dim'])
        self.console.print(Panel(header, title='Job Complete', border_style=color))

        # Show discovered assets (e.g., from portscan, subdomain)
        if assets:
            table = Table(title=f'Discovered Assets ({len(assets)})', border_style=self.colors['primary'])
            table.add_column('Key', style=self.colors['primary'])
            table.add_column('Name', style='white')
            table.add_column('Class', style=self.colors['accent'])
            table.add_column('Status', style=self.colors['dim'])
            for a in assets[:20]:
                table.add_row(
                    a.get('key', ''), a.get('name', a.get('dns', '')),
                    a.get('class', ''), a.get('status', ''),
                )
            self.console.print(table)
            if len(assets) > 20:
                self.console.print(f'[dim]...and {len(assets) - 20} more[/dim]')

        # Show attributes (e.g., open ports from portscan)
        if attributes:
            table = Table(title=f'Attributes ({len(attributes)})', border_style=self.colors['primary'])
            table.add_column('Name', style=f'bold {self.colors["primary"]}')
            table.add_column('Value', style='white')
            for attr in attributes[:30]:
                table.add_row(attr.get('name', ''), str(attr.get('value', '')))
            self.console.print(table)
            if len(attributes) > 30:
                self.console.print(f'[dim]...and {len(attributes) - 30} more[/dim]')

        # Show findings/risks
        if risks:
            table = Table(title=f'Findings ({len(risks)})', border_style=self.colors['error'])
            table.add_column('Risk', style=f'bold {self.colors["primary"]}')
            table.add_column('Severity', style=self.colors['accent'])
            table.add_column('Asset', style='white')
            table.add_column('Status', style=self.colors['dim'])
            for r in risks[:20]:
                name = r.get('name', r.get('title', ''))
                priority = r.get('priority', '')
                severity_map = {0: 'CRITICAL', 10: 'HIGH', 20: 'MEDIUM', 30: 'LOW', 40: 'INFO', 60: 'EXPOSURE'}
                severity = severity_map.get(priority, str(priority))
                table.add_row(name, severity, r.get('dns', ''), r.get('status', ''))
            self.console.print(table)
            if len(risks) > 20:
                self.console.print(f'[dim]...and {len(risks) - 20} more[/dim]')
