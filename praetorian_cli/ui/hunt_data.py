from rich import box
from rich.console import Group
from rich.panel import Panel
from rich.table import Table
from rich.text import Text


SEVERITY_CODES = {
    'critical': 'C',
    'high': 'H',
    'medium': 'M',
    'low': 'L',
    'info': 'I',
    'exposure': 'E',
}
SEVERITY_STYLES = {
    'critical': 'bold red',
    'high': 'red',
    'medium': 'yellow',
    'low': 'cyan',
    'info': 'blue',
    'exposure': 'dim',
}


def filter_hunt_findings(findings, status=None, severity=None):
    """Apply the Hunt UI's status and severity filters to risk records."""
    status_query = str(status or '').strip().lower()
    severity_query = str(severity or '').strip().lower()
    filtered = []
    for finding in findings or []:
        risk = _risk_record(finding)
        status_code = str(risk.get('status') or '').lower()
        status_label = str(risk.get('statusLabel') or '').lower()
        if status_query and not (
            status_code.startswith(status_query)
            or status_label.startswith(status_query)
        ):
            continue
        if severity_query and not _matches_severity(
            status_code,
            status_label,
            severity_query,
        ):
            continue
        filtered.append(finding)
    return filtered


def build_hunt_findings(findings, show_details=False):
    findings = list(findings or [])
    if not findings:
        return Panel(
            Text('No vulnerabilities found for this Hunt.', style='dim'),
            title='Hunt vulnerabilities',
            border_style='dim',
            box=box.ROUNDED,
        )

    table = Table(
        title=Text(f'Hunt vulnerabilities · {len(findings)}', style='bold red'),
        box=box.ROUNDED,
        border_style='red',
        expand=True,
        header_style='bold',
    )
    table.add_column('SEVERITY', width=10)
    table.add_column('STATUS', width=18)
    table.add_column('TARGET', min_width=16, ratio=2)
    table.add_column('VULNERABILITY', min_width=24, ratio=3)
    table.add_column('SOURCE', min_width=12, ratio=1)

    for finding in findings:
        risk = _risk_record(finding)
        severity = _severity(risk)
        table.add_row(
            Text(severity.upper(), style=SEVERITY_STYLES.get(severity, 'white')),
            Text(_risk_status(risk)),
            Text(_safe(risk.get('dns') or '—', 80)),
            Text(_safe(risk.get('title') or risk.get('name') or '—', 120), style='bold'),
            Text(_safe(risk.get('source') or '—', 80)),
        )

    if not show_details:
        return table
    details = [_finding_detail(finding) for finding in findings]
    return Group(table, Text(''), *details)


def build_hunt_memory(items):
    if not items:
        return Panel(
            Text('No memory items yet.', style='dim'),
            title='Hunt memory',
            border_style='dim',
            box=box.ROUNDED,
        )
    table = Table(
        title=Text(f'Hunt memory · {len(items)} items', style='bold magenta'),
        box=box.ROUNDED,
        border_style='magenta',
        expand=True,
        header_style='bold',
    )
    table.add_column('TITLE', min_width=24, ratio=2)
    table.add_column('UPDATED', min_width=20, ratio=1)
    for item in items:
        table.add_row(
            Text(_safe(item.get('title') or item.get('name'), 128), style='bold'),
            Text(_safe(item.get('updated') or item.get('created') or '—', 40)),
        )
    return table


def build_hunt_memory_item(title, content):
    return Panel(
        Text(_safe_multiline(content)),
        title=Text(f'◆ Memory · {title}', style='bold magenta'),
        border_style='magenta',
        box=box.ROUNDED,
        padding=(1, 2),
    )


def build_hunt_log(content):
    return Panel(
        Text(
            _safe_multiline(content) if content else 'No log entries yet.',
            style=None if content else 'dim',
        ),
        title=Text('Hannibal Hunt Log', style='bold cyan'),
        border_style='cyan' if content else 'dim',
        box=box.ROUNDED,
        padding=(1, 2),
    )


def _finding_detail(finding):
    risk = _risk_record(finding)
    key = _safe(risk.get('key') or 'unknown', 300)
    lines = []
    if risk.get('comment'):
        lines.append(('Comment', risk['comment']))
    if risk.get('cvss_score') is not None:
        lines.append(('CVSS', risk['cvss_score']))
    if risk.get('cwe_codes'):
        lines.append(('CWE', ', '.join(risk['cwe_codes'])))

    definition = finding.get('definition') if isinstance(finding, dict) else None
    if isinstance(definition, dict):
        for label, field in (
            ('Description', 'description'),
            ('Impact', 'impact'),
            ('Recommendation', 'recommendation'),
        ):
            if definition.get(field):
                lines.append((label, definition[field]))

    evidence = finding.get('evidence') if isinstance(finding, dict) else None
    if isinstance(evidence, list):
        for index, item in enumerate(evidence, start=1):
            if not isinstance(item, dict):
                continue
            source = item.get('source') or 'evidence'
            value = item.get('content') or item.get('value') or item.get('url') or item.get('path')
            lines.append((f'Evidence {index} · {source}', value or '—'))

    body = Text()
    body.append(f'{_risk_status(risk)} · {_safe(risk.get("dns") or "unknown target", 100)}\n', style='bold')
    body.append(key, style='cyan')
    for label, value in lines:
        body.append(f'\n\n{label}\n', style='bold bright_black')
        body.append(_safe(value, 4000))
    return Panel(
        body,
        title=Text(_safe(risk.get('title') or risk.get('name') or key, 120), style='bold'),
        border_style=SEVERITY_STYLES.get(_severity(risk), 'white').split()[-1],
        box=box.ROUNDED,
    )


def _risk_record(finding):
    if not isinstance(finding, dict):
        return {}
    nested = finding.get('risk')
    return nested if isinstance(nested, dict) else finding


def _matches_severity(status_code, status_label, severity):
    code = SEVERITY_CODES.get(severity, severity[:1].upper()).lower()
    return status_code.endswith(code) or status_label.endswith(severity)


def _severity(risk):
    label = str(risk.get('statusLabel') or '').strip().lower()
    for severity in SEVERITY_CODES:
        if label.endswith(severity):
            return severity
    code = str(risk.get('status') or '')[-1:].upper()
    return next(
        (severity for severity, suffix in SEVERITY_CODES.items() if suffix == code),
        'unknown',
    )


def _risk_status(risk):
    return _safe(risk.get('statusLabel') or risk.get('status') or 'unknown', 80)


def _safe_multiline(value):
    return ''.join(
        character if character in '\n\t' or character.isprintable() else ' '
        for character in str(value or '')
    )


def _safe(value, limit):
    printable = ''.join(
        character if character.isprintable() else ' '
        for character in str(value or '')
    )
    return ' '.join(printable.split())[:limit]
