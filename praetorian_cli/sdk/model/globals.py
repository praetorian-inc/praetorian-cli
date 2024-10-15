from enum import Enum


class Asset(Enum):
    ACTIVE = 'A'
    ACTIVE_HIGH = 'AH'
    ACTIVE_LOW = 'AL'
    FROZEN = 'F'
    FROZEN_LOW = 'FL'
    FROZEN_HIGH = 'FH'
    DELETED = 'D'


class Risk(Enum):
    DELETED = 'D'

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


class AddRisk(Enum):
    """ AddRisk is a subset of Risk. These are the only valid statuses when creating manual risks """
    TRIAGE_INFO = 'TI'
    TRIAGE_LOW = 'TL'
    TRIAGE_MEDIUM = 'TM'
    TRIAGE_HIGH = 'TH'
    TRIAGE_CRITICAL = 'TC'
