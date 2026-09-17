from praetorian_cli.ui.hunt_data import (
    build_hunt_findings,
    build_hunt_log,
    build_hunt_memory,
    filter_hunt_findings,
)


def _render(renderable):
    from io import StringIO
    from rich.console import Console

    output = StringIO()
    Console(file=output, width=120, color_system=None).print(renderable)
    return output.getvalue()


def test_hunt_findings_filter_and_dashboard():
    findings = [
        {
            'key': '#risk#db.example#sql-injection',
            'dns': 'db.example',
            'title': 'SQL injection',
            'status': 'OH',
            'statusLabel': 'Open High',
            'source': 'hannibal',
        },
        {
            'key': '#risk#web.example#headers',
            'dns': 'web.example',
            'title': 'Missing headers',
            'status': 'TM',
            'statusLabel': 'Detected Medium',
            'source': 'hannibal',
        },
    ]

    selected = filter_hunt_findings(
        findings,
        status='open',
        severity='high',
    )
    rendered = _render(build_hunt_findings(selected))

    assert selected == [findings[0]]
    assert 'SQL injection' in rendered
    assert 'Open High' in rendered
    assert 'Missing headers' not in rendered


def test_hunt_finding_severity_uses_wire_severity_not_deletion_reason():
    finding = {
        'key': '#risk#db.example#deleted-critical',
        'status': 'DCF',
        'statusLabel': '',
    }

    assert filter_hunt_findings([finding], severity='critical') == [finding]
    assert filter_hunt_findings([finding], severity='exposure') == []


def test_hunt_finding_details_include_evidence():
    hydrated = [{
        'risk': {
            'key': '#risk#db.example#sql-injection',
            'dns': 'db.example',
            'title': 'SQL injection',
            'statusLabel': 'Open Critical',
        },
        'definition': {'impact': 'Database compromise'},
        'evidence': [{
            'source': 'file',
            'path': 'proofs/db/sql',
            'content': 'Boolean response confirmed',
        }],
    }]

    rendered = _render(build_hunt_findings(hydrated, show_details=True))

    assert 'Database compromise' in rendered
    assert 'Boolean response confirmed' in rendered


def test_hunt_memory_and_log_render_empty_and_populated_states():
    memory = _render(build_hunt_memory([{
        'title': 'target-notes.md',
        'bytes': 2048,
        'updated': '2026-01-01T00:00:00Z',
    }]))
    log = _render(build_hunt_log('[iteration-complete] found SMB'))

    assert 'target-notes.md' in memory
    assert '2026-01-01T00:00:00Z' in memory
    assert 'Hannibal Hunt Log' in log
    assert 'found SMB' in log
