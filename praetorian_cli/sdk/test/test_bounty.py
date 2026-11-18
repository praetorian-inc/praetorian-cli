import pytest

from praetorian_cli.sdk.entities.bounty import (
    Bounty,
    PROOF_DEMONSTRATED,
    PROOF_DETECTED,
    PROOF_VERIFIED,
    filter_findings,
    hackerone_submissions,
    normalize_finding,
    normalize_severities,
    proof_level,
    select_tenants,
    sort_findings,
    tenant_program,
)

TENANT = {'account': 'guard+zebra_vdp-npo@praetorian.com', 'program': 'zebra_vdp'}


def risk(key, status, **extra):
    name = key.split('#')[-1]
    return {'key': key, 'name': name, 'dns': key.split('#')[2], 'status': status, 'title': name} | extra


def test_tenant_program_parses_bug_bounty_accounts_only():
    assert tenant_program('guard+bookingcom-lwy@praetorian.com') == 'bookingcom'
    assert tenant_program('guard+lowes_companies_vdp-btm@praetorian.com') == 'lowes_companies_vdp'
    assert tenant_program('guard+booking_holdings_inc_2026062501-cxm@praetorian.com') == 'booking_holdings_inc_2026062501'
    assert tenant_program('someone@praetorian.com') is None
    assert tenant_program('guard+acme-abc@example.com') is None
    assert tenant_program('') is None
    assert tenant_program(None) is None


def test_select_tenants_matches_slug_or_account_case_insensitively():
    tenants = [
        {'account': 'guard+costco-0z2@praetorian.com', 'program': 'costco'},
        {'account': 'guard+costco-2v0@praetorian.com', 'program': 'costco'},
        {'account': 'guard+lowes_companies_vdp-btm@praetorian.com', 'program': 'lowes_companies_vdp'},
    ]
    assert select_tenants(tenants, None) == tenants
    assert select_tenants(tenants, []) == tenants
    assert select_tenants(tenants, 'LOWES') == tenants[2:]
    assert select_tenants(tenants, ['costco-2v0']) == tenants[1:2]
    assert len(select_tenants(tenants, ['costco', 'lowes'])) == 3


def test_proof_level_prefers_verification_over_demonstration():
    assert proof_level({'proposedBy': 'cato-agent'}) == PROOF_VERIFIED
    assert proof_level({'publishedEvidence': '**Verified by Praetorian Guard — 2026-08-14**\n...'}) == PROOF_VERIFIED
    assert proof_level({'proposedEvidence': '  **Verified by Praetorian Guard'}) == PROOF_VERIFIED
    assert proof_level({'tags': ['cato-reviewed']}) == PROOF_VERIFIED
    assert proof_level({'demonstrated': '2026-08-14T10:07:51Z'}) == PROOF_DEMONSTRATED
    assert proof_level({'proposedBy': 'romulus-agent', 'proposedEvidence': 'curl ...'}) == PROOF_DEMONSTRATED
    assert proof_level({'source': 'nuclei'}) == PROOF_DETECTED
    assert proof_level({'publishedEvidence': None, 'tags': None}) == PROOF_DETECTED


def test_hackerone_submissions_only_uses_risk_sourced_attributes():
    risk_key = '#risk#https://knlaap.reflexisinc.com#reflected-xss-prelogin-broadcast'
    attributes = [
        {'name': 'hackerone-intent-id', 'value': '343698', 'source': risk_key},
        {'name': 'hackerone-status', 'value': 'pending', 'source': risk_key},
        {'name': 'hackerone-program', 'value': 'zebra_vdp', 'source': risk_key},
        {'name': 'hackerone-source', 'value': 'hacker-api', 'source': risk_key},
        # account-global integration status; not a per-risk submission
        {'name': 'hackerone-report-3609050-status', 'value': 'duplicate', 'source': '#integration#hackerone#att'},
        # unrelated attribute on a risk
        {'name': 'cvss', 'value': '9.8', 'source': risk_key},
    ]
    submissions = hackerone_submissions(attributes)
    assert list(submissions) == [risk_key]
    assert submissions[risk_key] == {
        'intent_id': '343698', 'status': 'pending', 'program': 'zebra_vdp', 'source': 'hacker-api',
    }


def test_normalize_finding_flattens_status_and_submission():
    record = risk('#risk#https://a.example#sqli', 'OC', cvss_score=9.8, proposedBy='cato-agent',
                  tags=['cato-reviewed'], created='2026-08-01T00:00:00Z', updated='2026-08-02T00:00:00Z')
    finding = normalize_finding(TENANT, record, {'intent_id': '1', 'status': 'pending', 'program': 'zebra_vdp'})
    assert finding['program'] == 'zebra_vdp'
    assert finding['account'] == TENANT['account']
    assert finding['state'] == 'open'
    assert finding['severity'] == 'critical'
    assert finding['proof'] == PROOF_VERIFIED
    assert finding['cvss_score'] == 9.8
    assert finding['hackerone'] == {'submitted': True, 'intent_id': '1', 'status': 'pending', 'program': 'zebra_vdp'}

    unsubmitted = normalize_finding(TENANT, risk('#risk#b.example#x', 'TH'))
    assert unsubmitted['state'] == 'triage'
    assert unsubmitted['severity'] == 'high'
    assert unsubmitted['proof'] == PROOF_DETECTED
    assert unsubmitted['hackerone']['submitted'] is False
    assert unsubmitted['hackerone']['intent_id'] is None


def test_normalize_severities_accepts_codes_names_and_all():
    assert normalize_severities(None) is None
    assert normalize_severities('all') is None
    assert normalize_severities('critical,high') == {'C', 'H'}
    assert normalize_severities(['C', 'h', 'Medium']) == {'C', 'H', 'M'}
    assert normalize_severities(('C', 'H')) == {'C', 'H'}
    with pytest.raises(ValueError):
        normalize_severities('urgent')


def _sample_findings():
    return [
        normalize_finding(TENANT, risk('#risk#a#detected-crit', 'TC')),
        normalize_finding(TENANT, risk('#risk#b#verified-high', 'OH', proposedBy='cato-agent', cvss_score=7.5),
                          {'intent_id': '9', 'status': 'pending'}),
        normalize_finding(TENANT, risk('#risk#c#demo-high', 'TH', demonstrated='2026-01-01T00:00:00Z')),
        normalize_finding(TENANT, risk('#risk#d#deleted-fp', 'DCF', proposedBy='cato-agent')),
        normalize_finding(TENANT, risk('#risk#e#medium', 'OM')),
    ]


def test_filter_findings_by_severity_state_proof_and_submission():
    findings = _sample_findings()

    live_crit_high = filter_findings(findings, severities=('C', 'H'), states=('T', 'O'))
    assert [f['name'] for f in live_crit_high] == ['detected-crit', 'verified-high', 'demo-high']

    everything = filter_findings(findings, severities=None, states=None)
    assert len(everything) == 5

    deleted = filter_findings(findings, severities='all', states=('D',))
    assert [f['name'] for f in deleted] == ['deleted-fp']

    verified = filter_findings(findings, severities=None, states=None, proof=PROOF_VERIFIED)
    assert {f['name'] for f in verified} == {'verified-high', 'deleted-fp'}

    at_least_demo = filter_findings(findings, severities=None, states=None, proof=PROOF_DEMONSTRATED)
    assert {f['name'] for f in at_least_demo} == {'verified-high', 'deleted-fp', 'demo-high'}

    unsubmitted = filter_findings(findings, severities=None, states=None, submitted=False)
    assert 'verified-high' not in {f['name'] for f in unsubmitted}
    assert [f['name'] for f in filter_findings(findings, severities=None, states=None, submitted=True)] == ['verified-high']

    with pytest.raises(ValueError):
        filter_findings(findings, proof='guessed')


def test_sort_findings_ranks_severity_then_proof():
    findings = _sample_findings()

    by_severity = [f['name'] for f in sort_findings(findings, 'severity')]
    assert by_severity == ['deleted-fp', 'detected-crit', 'verified-high', 'demo-high', 'medium']

    by_proof = [f['name'] for f in sort_findings(findings, 'proof')]
    assert by_proof[:2] == ['deleted-fp', 'verified-high']
    assert by_proof[-1] == 'medium' or by_proof[-1] == 'detected-crit'

    by_cvss = [f['name'] for f in sort_findings(findings, 'cvss')]
    assert by_cvss[0] == 'verified-high'

    assert [f['name'] for f in sort_findings(findings, 'severity', descending=True)] == list(reversed(by_severity))

    with pytest.raises(ValueError):
        sort_findings(findings, 'vibes')


def test_sort_findings_by_timestamp_newest_first():
    findings = [
        normalize_finding(TENANT, risk('#risk#a#old', 'OH', created='2026-01-01T00:00:00Z')),
        normalize_finding(TENANT, risk('#risk#b#new', 'OH', created='2026-06-01T00:00:00Z')),
        normalize_finding(TENANT, risk('#risk#c#missing', 'OH')),
    ]
    assert [f['name'] for f in sort_findings(findings, 'created')] == ['new', 'old', 'missing']


class FakeSearch:
    def __init__(self, accounts):
        self.accounts = accounts

    def by_key_prefix(self, prefix, offset=None, pages=1):
        return self.accounts, None


class FakeAccounts:
    def __init__(self, accounts):
        self.accounts = accounts

    def list(self, *args, **kwargs):
        return self.accounts, None


class FakeApi:
    def __init__(self, accounts):
        self.accounts = FakeAccounts(accounts)


def test_tenants_lists_bug_bounty_accounts_sorted_and_deduplicated():
    me = 'engineer@praetorian.com'
    accounts = [
        {'name': 'guard+zebra_vdp-npo@praetorian.com', 'member': me},
        {'name': 'guard+att-4n4@praetorian.com', 'member': me},
        {'name': 'guard+att-4n4@praetorian.com', 'member': 'other@praetorian.com'},
        {'name': 'customer@example.com', 'member': me},
        {'name': me, 'member': 'collaborator@praetorian.com'},
    ]
    bounty = Bounty(FakeApi(accounts))
    assert bounty.tenants() == [
        {'account': 'guard+att-4n4@praetorian.com', 'program': 'att'},
        {'account': 'guard+zebra_vdp-npo@praetorian.com', 'program': 'zebra_vdp'},
    ]
    assert bounty.tenants(['zebra']) == [{'account': 'guard+zebra_vdp-npo@praetorian.com', 'program': 'zebra_vdp'}]


def test_findings_aggregates_tenants_and_reports_errors(monkeypatch):
    me = 'engineer@praetorian.com'
    accounts = [
        {'name': 'guard+att-4n4@praetorian.com', 'member': me},
        {'name': 'guard+broken-xyz@praetorian.com', 'member': me},
    ]
    bounty = Bounty(FakeApi(accounts))

    class FakeRisks:
        def list(self):
            return [
                risk('#risk#https://x.att.com#ato', 'OC', proposedBy='cato-agent'),
                risk('#risk#https://y.att.com#nuclei-thing', 'TH'),
                risk('#risk#https://z.att.com#fp', 'DHF'),
            ], None

    class FakeAttributes:
        def list(self, prefix_filter='', **kwargs):
            assert prefix_filter == 'hackerone-'
            return [{'name': 'hackerone-intent-id', 'value': '7', 'source': '#risk#https://x.att.com#ato'}], None

    class FakeTenantSdk:
        risks = FakeRisks()
        attributes = FakeAttributes()

    def fake_tenant_sdk(account):
        if 'broken' in account:
            raise RuntimeError('boom')
        return FakeTenantSdk()

    monkeypatch.setattr(bounty, '_tenant_sdk', fake_tenant_sdk)

    findings, errors = bounty.findings(workers=2)
    assert [f['name'] for f in findings] == ['ato', 'nuclei-thing']
    assert findings[0]['hackerone']['submitted'] is True
    assert findings[1]['hackerone']['submitted'] is False
    assert errors == [{'account': 'guard+broken-xyz@praetorian.com', 'program': 'broken', 'error': 'boom'}]

    verified_unsubmitted, _ = bounty.findings(proof=PROOF_VERIFIED, submitted=False)
    assert verified_unsubmitted == []

    all_states, _ = bounty.findings(severities=None, states=None, programs=['att'])
    assert len(all_states) == 3


def test_handler_rows_render_as_tsv_and_table():
    from io import StringIO

    from rich.console import Console

    from praetorian_cli.handlers.bounty import build_findings_table, findings_tsv

    findings = [
        normalize_finding(TENANT, risk('#risk#https://a.example#ato', 'OC', proposedBy='cato-agent', cvss_score=9.8),
                          {'intent_id': '1', 'status': 'pending'}),
        normalize_finding(TENANT, risk('#risk#https://b.example#nuclei-thing', 'TH')),
    ]
    lines = list(findings_tsv(findings))
    assert lines[0] == 'program\tseverity\tstate\tproof\th1\tcvss\tkey'
    assert lines[1] == 'zebra_vdp\tcritical\topen\tverified\tpending\t9.8\t#risk#https://a.example#ato'
    assert lines[2] == 'zebra_vdp\thigh\ttriage\tdetected\t-\t-\t#risk#https://b.example#nuclei-thing'

    output = StringIO()
    Console(file=output, width=160, color_system=None).print(build_findings_table(findings))
    rendered = output.getvalue()
    assert '2 bug bounty findings' in rendered
    assert '#risk#https://a.example#ato' in rendered
    assert 'pending' in rendered
