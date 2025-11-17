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

class Preseed(Enum):
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

    OPEN_EXPOSURE = 'OE'
    OPEN_INFO = 'OI'
    OPEN_LOW = 'OL'
    OPEN_MEDIUM = 'OM'
    OPEN_HIGH = 'OH'
    OPEN_CRITICAL = 'OC'

    ACCEPTED_EXPOSURE = 'IE'
    ACCEPTED_INFO = 'II'
    ACCEPTED_LOW = 'IL'
    ACCEPTED_MEDIUM = 'IM'
    ACCEPTED_HIGH = 'IH'
    ACCEPTED_CRITICAL = 'IC'

    REMEDIATED_EXPOSURE = 'RE'
    REMEDIATED_INFO = 'RI'
    REMEDIATED_LOW = 'RL'
    REMEDIATED_MEDIUM = 'RM'
    REMEDIATED_HIGH = 'RH'
    REMEDIATED_CRITICAL = 'RC'

    DELETED_FALSE_POSITIVE_EXPOSURE = 'DEF'
    DELETED_FALSE_POSITIVE_INFO = 'DIF'
    DELETED_FALSE_POSITIVE_LOW = 'DLF'
    DELETED_FALSE_POSITIVE_MEDIUM = 'DMF'
    DELETED_FALSE_POSITIVE_HIGH = 'DHF'
    DELETED_FALSE_POSITIVE_CRITICAL = 'DCF'

    DELETED_OUT_OF_SCOPE_EXPOSURE = 'DES'
    DELETED_OUT_OF_SCOPE_INFO = 'DIS'
    DELETED_OUT_OF_SCOPE_LOW = 'DLS'
    DELETED_OUT_OF_SCOPE_MEDIUM = 'DMS'
    DELETED_OUT_OF_SCOPE_HIGH = 'DHS'
    DELETED_OUT_OF_SCOPE_CRITICAL = 'DCS'

    DELETED_DUPLICATE_EXPOSURE = 'DED'
    DELETED_DUPLICATE_INFO = 'DID'
    DELETED_DUPLICATE_LOW = 'DLD'
    DELETED_DUPLICATE_MEDIUM = 'DMD'
    DELETED_DUPLICATE_HIGH = 'DHD'
    DELETED_DUPLICATE_CRITICAL = 'DCD'

    DELETED_OTHER_EXPOSURE = 'DEO'
    DELETED_OTHER_INFO = 'DIO'
    DELETED_OTHER_LOW = 'DLO'
    DELETED_OTHER_MEDIUM = 'DMO'
    DELETED_OTHER_HIGH = 'DHO'
    DELETED_OTHER_CRITICAL = 'DCO'


class AddRisk(Enum):
    """ AddRisk is a subset of Risk. These are the only valid statuses when creating manual risks """
    TRIAGE_INFO = Risk.TRIAGE_INFO.value
    TRIAGE_LOW = Risk.TRIAGE_LOW.value
    TRIAGE_MEDIUM = Risk.TRIAGE_MEDIUM.value
    TRIAGE_HIGH = Risk.TRIAGE_HIGH.value
    TRIAGE_CRITICAL = Risk.TRIAGE_CRITICAL.value


class AgentType(Enum):
    AFFILIATION = 'affiliation'
    AUTO_TRIAGE = 'autotriage'


class Kind(Enum):
    ASSET = 'asset'
    REPOSITORY = 'repository'
    INTEGRATION = 'integration'
    ADDOMAIN = 'addomain'
    RISK = 'risk'
    ATTRIBUTE = 'attribute'
    SEED = 'seed'
    PRESEED = 'preseed'
    OTHERS = 'others'
    WEBAPPLICATION = 'webapplication'
    WEBPAGE = 'webpage'
    PORT = 'port'

EXACT_FLAG = {'exact': 'true'}
DESCENDING_FLAG = {'desc': 'true'}
GLOBAL_FLAG = {'global': 'true'}
USER_FLAG = {'user': 'true'}
