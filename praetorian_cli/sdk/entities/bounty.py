"""Bug bounty findings feed.

Aggregates risks across the bug bounty tenants the current principal can
access, tags each one with how well it is proven and whether it has already
been pushed to HackerOne, and returns a flat list that can be filtered and
sorted to surface the highest-value submissions first.
"""
import re
from concurrent.futures import ThreadPoolExecutor

from praetorian_cli.sdk.keychain import Keychain

# Bug bounty tenants are provisioned as guard+<program>-<3 char suffix>@praetorian.com
TENANT_PATTERN = re.compile(r'^guard\+(?P<slug>.+)-[a-z0-9]{3}@praetorian\.com$')

SEVERITY_ORDER = {'C': 0, 'H': 1, 'M': 2, 'L': 3, 'I': 4, 'E': 5}
SEVERITY_NAMES = {'C': 'critical', 'H': 'high', 'M': 'medium', 'L': 'low', 'I': 'info', 'E': 'exposure'}
SEVERITY_ALIASES = {name: code for code, name in SEVERITY_NAMES.items()} | {code.lower(): code for code in SEVERITY_NAMES}

STATE_NAMES = {'T': 'triage', 'O': 'open', 'I': 'accepted', 'R': 'remediated', 'D': 'deleted'}
LIVE_STATES = ('T', 'O')

PROOF_VERIFIED = 'verified'
PROOF_DEMONSTRATED = 'demonstrated'
PROOF_DETECTED = 'detected'
PROOF_ORDER = {PROOF_VERIFIED: 0, PROOF_DEMONSTRATED: 1, PROOF_DETECTED: 2}

VERIFIED_EVIDENCE_PREFIX = '**Verified by Praetorian Guard'
VERIFIER_AGENTS = ('cato-agent',)
VERIFIED_TAGS = ('cato-reviewed', 'cato-proposed')

H1_ATTRIBUTE_PREFIX = 'hackerone-'
H1_FIELDS = ('intent-id', 'status', 'program', 'source')

SORT_FIELDS = ('severity', 'proof', 'created', 'updated', 'program', 'cvss')


class Bounty:
    """ The methods in this class are to be accessed from sdk.bounty, where sdk is an instance
    of Chariot. """

    def __init__(self, api):
        self.api = api

    def tenants(self, program_filter=None):
        """
        List the bug bounty tenants the current principal can access.

        :param program_filter: Only return tenants whose program slug or account contains any of these strings
        :type program_filter: list[str] or str or None
        :return: List of dicts with 'account' (email) and 'program' (tenant slug)
        :rtype: list
        """
        accounts, _ = self.api.accounts.list()
        tenants = []
        seen = set()
        for account in accounts:
            email = account.get('name', '')
            slug = tenant_program(email)
            if not slug or email in seen:
                continue
            seen.add(email)
            tenants.append({'account': email, 'program': slug})
        tenants = select_tenants(tenants, program_filter)
        return sorted(tenants, key=lambda t: (t['program'], t['account']))

    def findings(self, programs=None, severities=('C', 'H'), states=LIVE_STATES, proof=None, submitted=None,
                 sort_by='severity', descending=False, workers=4):
        """
        Feed of bug bounty findings across tenants, normalized for H1 submission triage.

        :param programs: Restrict to tenants whose program slug or account matches any of these strings
        :type programs: list[str] or None
        :param severities: Severity codes to include (C, H, M, L, I, E). None or empty means all
        :type severities: tuple or list or None
        :param states: Risk state codes to include (T, O, I, R, D). None or empty means all
        :type states: tuple or list or None
        :param proof: Minimum proof level: 'verified', 'demonstrated' or 'detected' (None means any)
        :type proof: str or None
        :param submitted: True for findings already pushed to HackerOne, False for not yet pushed, None for both
        :type submitted: bool or None
        :param sort_by: One of severity, proof, created, updated, program, cvss
        :type sort_by: str
        :param descending: Reverse the sort order
        :type descending: bool
        :param workers: Number of tenants to query concurrently
        :type workers: int
        :return: Tuple of (list of normalized findings, list of per-tenant errors)
        :rtype: tuple
        """
        tenants = self.tenants(programs)
        findings = []
        errors = []

        with ThreadPoolExecutor(max_workers=max(1, workers)) as pool:
            for tenant, tenant_findings, error in pool.map(self._tenant_findings, tenants):
                if error:
                    errors.append({'account': tenant['account'], 'program': tenant['program'], 'error': error})
                findings.extend(tenant_findings)

        findings = filter_findings(findings, severities=severities, states=states, proof=proof, submitted=submitted)
        return sort_findings(findings, sort_by, descending), errors

    def _tenant_findings(self, tenant):
        try:
            sdk = self._tenant_sdk(tenant['account'])
            risks, _ = sdk.risks.list()
            attributes, _ = sdk.attributes.list(prefix_filter=H1_ATTRIBUTE_PREFIX)
        except Exception as e:
            return tenant, [], str(e) or type(e).__name__

        submissions = hackerone_submissions(attributes)
        findings = [normalize_finding(tenant, risk, submissions.get(risk.get('key'), {})) for risk in risks]
        return tenant, findings, None

    def _tenant_sdk(self, account):
        """ A Chariot client assumed into `account` that shares this client's loaded keychain,
        so concurrent tenant queries never re-read the keychain file or re-authenticate. """
        from praetorian_cli.sdk.chariot import Chariot

        base = self.api.keychain
        base.token()
        keychain = Keychain(profile=base.profile, account=account, data=base.data, filepath=base.filepath)
        keychain.config = base.config
        keychain._loaded = True
        keychain.token_cache = base.token_cache
        keychain.token_expiry = base.token_expiry
        return Chariot(keychain=keychain, proxy=self.api.proxy)


def tenant_program(email):
    """ Program slug for a bug bounty tenant email, or None when the email is not a BB tenant. """
    match = TENANT_PATTERN.match(email or '')
    return match.group('slug') if match else None


def select_tenants(tenants, program_filter):
    if not program_filter:
        return list(tenants)
    if isinstance(program_filter, str):
        program_filter = [program_filter]
    needles = [p.lower() for p in program_filter if p]
    if not needles:
        return list(tenants)
    return [t for t in tenants
            if any(n in t['program'].lower() or n in t['account'].lower() for n in needles)]


def hackerone_submissions(attributes):
    """ Map risk key -> {'intent_id', 'status', 'program', 'source'} from risk-sourced
    hackerone-* attributes written by the hackerone-submit capability. Integration-level
    report status attributes (hackerone-report-<id>-status) are account-global and skipped. """
    submissions = {}
    for attribute in attributes:
        source = attribute.get('source', '')
        name = attribute.get('name', '')
        if not source.startswith('#risk#') or not name.startswith(H1_ATTRIBUTE_PREFIX):
            continue
        field = name[len(H1_ATTRIBUTE_PREFIX):]
        if field not in H1_FIELDS:
            continue
        submissions.setdefault(source, {})[field.replace('-', '_')] = attribute.get('value', '')
    return submissions


def proof_level(risk):
    """ How well a finding is proven: verified (independent agent verification), demonstrated
    (working proof attached), or detected (scanner signal only). """
    if risk.get('proposedBy') in VERIFIER_AGENTS:
        return PROOF_VERIFIED
    for evidence in (risk.get('publishedEvidence'), risk.get('proposedEvidence')):
        if isinstance(evidence, str) and evidence.lstrip().startswith(VERIFIED_EVIDENCE_PREFIX):
            return PROOF_VERIFIED
    if any(tag in VERIFIED_TAGS for tag in risk.get('tags') or []):
        return PROOF_VERIFIED
    if risk.get('demonstrated') or risk.get('publishedEvidence') or risk.get('proposedEvidence'):
        return PROOF_DEMONSTRATED
    return PROOF_DETECTED


def normalize_finding(tenant, risk, submission=None):
    status = risk.get('status') or ''
    state = status[0:1]
    severity = status[1:2]
    submission = submission or {}
    hackerone = {
        'submitted': bool(submission),
        'intent_id': submission.get('intent_id'),
        'status': submission.get('status'),
        'program': submission.get('program'),
    }
    return {
        'account': tenant['account'],
        'program': tenant['program'],
        'key': risk.get('key', ''),
        'dns': risk.get('dns', ''),
        'name': risk.get('name', ''),
        'title': risk.get('title') or risk.get('name', ''),
        'status': status,
        'state': STATE_NAMES.get(state, state),
        'severity': SEVERITY_NAMES.get(severity, severity),
        'proof': proof_level(risk),
        'cvss_score': risk.get('cvss_score'),
        'source': risk.get('source', ''),
        'origins': risk.get('origins') or [],
        'tags': risk.get('tags') or [],
        'proposed_by': risk.get('proposedBy'),
        'proposed_comment': risk.get('proposedComment'),
        'created': risk.get('created', ''),
        'updated': risk.get('updated', ''),
        'demonstrated': risk.get('demonstrated'),
        'hackerone': hackerone,
    }


def normalize_severities(severities):
    """ Accept codes (C, H) or names (critical, high) in any case; None/empty/'all' means no filter. """
    if not severities:
        return None
    if isinstance(severities, str):
        severities = severities.split(',')
    codes = set()
    for value in severities:
        value = (value or '').strip().lower()
        if not value:
            continue
        if value == 'all':
            return None
        code = SEVERITY_ALIASES.get(value)
        if code is None:
            raise ValueError(f'Unknown severity "{value}". Use one of: {", ".join(SEVERITY_NAMES.values())}')
        codes.add(code)
    return codes or None


def filter_findings(findings, severities=None, states=None, proof=None, submitted=None):
    severities = normalize_severities(severities)
    states = set(states) if states else None
    if proof is not None and proof not in PROOF_ORDER:
        raise ValueError(f'Unknown proof level "{proof}". Use one of: {", ".join(PROOF_ORDER)}')

    selected = []
    for finding in findings:
        status = finding.get('status', '')
        if severities is not None and status[1:2] not in severities:
            continue
        if states is not None and status[0:1] not in states:
            continue
        if proof is not None and PROOF_ORDER[finding['proof']] > PROOF_ORDER[proof]:
            continue
        if submitted is not None and finding['hackerone']['submitted'] != submitted:
            continue
        selected.append(finding)
    return selected


def sort_findings(findings, sort_by='severity', descending=False):
    if sort_by not in SORT_FIELDS:
        raise ValueError(f'Unknown sort field "{sort_by}". Use one of: {", ".join(SORT_FIELDS)}')

    def rank(finding):
        status = finding.get('status', '')
        severity = SEVERITY_ORDER.get(status[1:2], len(SEVERITY_ORDER))
        proof = PROOF_ORDER.get(finding.get('proof'), len(PROOF_ORDER))
        cvss = finding.get('cvss_score')
        cvss_rank = -float(cvss) if isinstance(cvss, (int, float)) else 0.0
        if sort_by == 'severity':
            return (severity, proof, cvss_rank, finding['program'], finding['key'])
        if sort_by == 'proof':
            return (proof, severity, cvss_rank, finding['program'], finding['key'])
        if sort_by == 'cvss':
            return (cvss_rank, severity, proof, finding['program'], finding['key'])
        if sort_by == 'program':
            return (finding['program'], severity, proof, finding['key'])
        # created / updated: newest first by default
        return (invert_timestamp(finding.get(sort_by, '')), severity, proof, finding['key'])

    return sorted(findings, key=rank, reverse=descending)


def invert_timestamp(value):
    """ Sort key that places the newest ISO-8601 timestamp first. """
    value = value or ''
    return ''.join(chr(0x10FFFF - ord(c)) for c in value) if value else '\U0010FFFF'
