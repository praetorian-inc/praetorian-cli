"""
This file contains the global constants in the Chariot backend API
"""
from enum import Enum


class Asset(Enum):
    ACTIVE = 'A'
    FROZEN = 'F'
    DELETED = 'D'
    PENDING = 'P'
    FROZEN_REJECTED = 'FR'


class Seed(Enum):
    ACTIVE = Asset.ACTIVE.value
    DELETED = Asset.DELETED.value
    PENDING = Asset.PENDING.value
    FROZEN = Asset.FROZEN.value
    FROZEN_REJECTED = Asset.FROZEN_REJECTED.value


class Risk(Enum):
    TRIAGE_INFO = 'TI'
    TRIAGE_LOW = 'TL'
    TRIAGE_MEDIUM = 'TM'
    TRIAGE_HIGH = 'TH'
    TRIAGE_CRITICAL = 'TC'

    IGNORED_EXPOSURE = 'IE'
    IGNORED_INFO = 'II'
    IGNORED_LOW = 'IL'
    IGNORED_MEDIUM = 'IM'
    IGNORED_HIGH = 'IH'
    IGNORED_CRITICAL = 'IC'

    OPEN_EXPOSURE = 'OE'
    OPEN_INFO = 'OI'
    OPEN_LOW = 'OL'
    OPEN_MEDIUM = 'OM'
    OPEN_HIGH = 'OH'
    OPEN_CRITICAL = 'OC'
    OPEN_MATERIAL = "OX"

    REMEDIATED_EXPOSURE = 'RE'
    REMEDIATED_INFO = 'RI'
    REMEDIATED_LOW = 'RL'
    REMEDIATED_MEDIUM = 'RM'
    REMEDIATED_HIGH = 'RH'
    REMEDIATED_CRITICAL = 'RC'
    REMEDIATED_MATERIAL = "RX"

    DELETED_EXPOSURE = 'DE'
    DELETED_INFO = 'DI'
    DELETED_LOW = 'DL'
    DELETED_MEDIUM = 'DM'
    DELETED_HIGH = 'DH'
    DELETED_CRITICAL = 'DC'


class AddRisk(Enum):
    """ AddRisk is a subset of Risk. These are the only valid statuses when creating manual risks """
    TRIAGE_INFO = Risk.TRIAGE_INFO.value
    TRIAGE_LOW = Risk.TRIAGE_LOW.value
    TRIAGE_MEDIUM = Risk.TRIAGE_MEDIUM.value
    TRIAGE_HIGH = Risk.TRIAGE_HIGH.value
    TRIAGE_CRITICAL = Risk.TRIAGE_CRITICAL.value


class AgentType(Enum):
    ATTRIBUTION = 'attribution'


CAPABILITIES = (
    'reverse-whois',
    'csp-mine',
    'tls-mine',
    'azuread-discovery',
    'edgar',
    'cidr',
    'favicon',
    'reverse-csp',
    'builtwith',
    'nuclei',
    'whois',
    'subdomain',
    'portscan',
    'github',
    'github-repository',
    'secrets',
    'amazon',
    'bitbucket',
    'azure',
    'gcp',
    'ns1',
    'cloudflare',
    'gato',
    'crawler',
    'gitlab',
    'ssh',
    'nessus',
    'nessus-import',
    'insightvm',
    'insightvm-import',
    'qualys',
    'qualys-import',
    'burp-enterprise',
    'ip',
    'website',
    'digitalocean',
    'burp-internal',
    'seed-import',
    'tenablevm',
)
