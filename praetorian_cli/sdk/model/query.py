from enum import Enum
from typing import Optional

from praetorian_cli.sdk.model.globals import GLOBAL_FLAG, Kind

DEFAULT_PAGE_SIZE = 4096


class Filter:
    class Operator(Enum):
        EQUAL = '='
        CONTAINS = 'CONTAINS'
        LESS_THAN = '<'
        LESS_THAN_OR_EQUAL = '<='
        LARGER_THAN = '>'
        LARGER_THAN_OR_EQUAL = '>='
        STARTS_WITH = 'STARTS WITH'
        ENDS_WITH = 'ENDS WITH'
        AND = "AND"
        OR = "OR"
        IN = "IN"

    class Field(Enum):
        KEY = 'key'
        GROUP = 'group'
        IDENTIFIER = 'identifier'
        DNS = 'dns'
        NAME = 'name'
        VALUE = 'value'
        STATUS = 'status'
        SOURCE = 'source'
        CREATED = 'created'
        REGISTRAR = 'registrar'
        EMAIL = 'email'
        LOCATION = 'location'
        PRIORITY = 'priority'
        CLASS = 'class'
        TYPE = 'type'
        TITLE = 'title'
        VISITED = 'visited'
        VENDOR = 'vendor'
        PRODUCT = 'product'
        VERSION = 'version'
        CPE = 'cpe'
        SURFACE = 'surface'
        ASNAME = 'asname'
        ASNUMBER = 'asnumber'
        CVSS = 'cvss'
        EPSS = 'epss'
        KEV = 'kev'
        EXPLOIT = 'exploit'
        PRIVATE = 'private'
        PRIMARY_URL = 'primary_url'
        URL = 'url'

        # Active Directory fields
        OBJECTID = 'objectid'
        SID = 'sid'
        DOMAIN = 'domain'
        LABEL = 'label'
        TAGS = 'tags'
        SAMACCOUNTNAME = 'samaccountname'
        DISPLAYNAME = 'displayname'
        DESCRIPTION = 'description'
        ADMINCOUNT = 'admincount'
        HASSPN = 'hasspn'
        HASLAPS = 'haslaps'
        DONTREQPREAUTH = 'dontreqpreauth'
        UNCONSTRAINEDDELEGATION = 'unconstraineddelegation'
        ENABLED = 'enabled'
        LASTLOGON = 'lastlogon'
        LASTLOGONTIMESTAMP = 'lastlogontimestamp'
        PWDLASTSET = 'pwdlastset'
        SENSITIVE = 'sensitive'
        ISDC = 'isdc'
        DNSHOSTNAME = 'dnshostname'
        OPERATINGSYSTEM = 'operatingsystem'
        GMSA = 'gmsa'
        TRUSTEDTOAUTH = 'trustedtoauth'
        GROUPSCOPE = 'groupscope'
        HIGHVALUE = 'highvalue'

    def __init__(self, field: Field, operator: Operator, value: str, not_: bool = False):
        self.field = field
        self.operator = operator
        self.value = value
        self.not_ = not_

    def to_dict(self) -> dict:
        return {'field': self.field.value, 'operator': self.operator.value, 'value': self.value, 'not': self.not_}


class Relationship:
    class Label(Enum):
        HAS_VULNERABILITY = 'HAS_VULNERABILITY'
        DISCOVERED = 'DISCOVERED'
        HAS_ATTRIBUTE = 'HAS_ATTRIBUTE'
        HAS_WEBPAGE = 'HAS_WEBPAGE'
        HAS_PORT = 'HAS_PORT'

        # AD: Ownership and Control
        OWNS = 'Owns'
        GENERIC_ALL = 'GenericAll'
        GENERIC_WRITE = 'GenericWrite'
        WRITE_OWNER = 'WriteOwner'
        WRITE_DACL = 'WriteDacl'

        # AD: Group Membership
        MEMBER_OF = 'MemberOf'

        # AD: Password Control
        FORCE_CHANGE_PASSWORD = 'ForceChangePassword'

        # AD: Extended Rights
        ALL_EXTENDED_RIGHTS = 'AllExtendedRights'
        ADD_MEMBER = 'AddMember'

        # AD: Sessions
        HAS_SESSION = 'HasSession'

        # AD: Container Relationships
        CONTAINS = 'Contains'

        # AD: GPO
        GPLINK = 'GPLink'

        # AD: Delegation
        ALLOWED_TO_DELEGATE = 'AllowedToDelegate'
        COERCE_TO_TGT = 'CoerceToTGT'

        # AD: Replication Rights
        GET_CHANGES = 'GetChanges'
        GET_CHANGES_ALL = 'GetChangesAll'
        GET_CHANGES_IN_FILTERED_SET = 'GetChangesInFilteredSet'

        # AD: Trust
        CROSS_FOREST_TRUST = 'CrossForestTrust'
        SAME_FOREST_TRUST = 'SameForestTrust'
        SPOOF_SID_HISTORY = 'SpoofSIDHistory'
        ABUSE_TGT_DELEGATION = 'AbuseTGTDelegation'

        # AD: Resource-Based Constrained Delegation
        ALLOWED_TO_ACT = 'AllowedToAct'

        # AD: Administrative Access
        ADMIN_TO = 'AdminTo'
        CAN_PS_REMOTE = 'CanPSRemote'
        CAN_RDP = 'CanRDP'
        EXECUTE_DCOM = 'ExecuteDCOM'

        # AD: SID History
        HAS_SID_HISTORY = 'HasSIDHistory'

        # AD: Self Rights
        ADD_SELF = 'AddSelf'

        # AD: DCSync
        DCSYNC = 'DCSync'

        # AD: Password Reading
        READ_LAPS_PASSWORD = 'ReadLAPSPassword'
        READ_GMSA_PASSWORD = 'ReadGMSAPassword'
        DUMP_SMSA_PASSWORD = 'DumpSMSAPassword'

        # AD: SQL
        SQL_ADMIN = 'SQLAdmin'

        # AD: Specific Write Rights
        ADD_ALLOWED_TO_ACT = 'AddAllowedToAct'
        WRITE_SPN = 'WriteSPN'
        ADD_KEY_CREDENTIAL_LINK = 'AddKeyCredentialLink'

        # AD: Local Group Membership
        LOCAL_TO_COMPUTER = 'LocalToComputer'
        MEMBER_OF_LOCAL_GROUP = 'MemberOfLocalGroup'
        REMOTE_INTERACTIVE_LOGON_RIGHT = 'RemoteInteractiveLogonRight'

        # AD: LAPS
        SYNC_LAPS_PASSWORD = 'SyncLAPSPassword'

        # AD: Write Permissions
        WRITE_ACCOUNT_RESTRICTIONS = 'WriteAccountRestrictions'
        WRITE_GPLINK = 'WriteGPLink'

        # AD: Certificate Authority
        ROOT_CA_FOR = 'RootCAFor'
        DC_FOR = 'DCFor'
        PUBLISHED_TO = 'PublishedTo'
        MANAGE_CERTIFICATES = 'ManageCertificates'
        MANAGE_CA = 'ManageCA'
        DELEGATED_ENROLLMENT_AGENT = 'DelegatedEnrollmentAgent'
        ENROLL = 'Enroll'
        HOSTS_CA_SERVICE = 'HostsCAService'
        WRITE_PKI_ENROLLMENT_FLAG = 'WritePKIEnrollmentFlag'
        WRITE_PKI_NAME_FLAG = 'WritePKINameFlag'
        NT_AUTH_STORE_FOR = 'NTAuthStoreFor'
        TRUSTED_FOR_NT_AUTH = 'TrustedForNTAuth'
        ENTERPRISE_CA_FOR = 'EnterpriseCAFor'
        ISSUED_SIGNED_BY = 'IssuedSignedBy'
        GOLDEN_CERT = 'GoldenCert'
        ENROLL_ON_BEHALF_OF = 'EnrollOnBehalfOf'

        # AD: Certificate Template Links
        OID_GROUP_LINK = 'OIDGroupLink'
        EXTENDED_BY_POLICY = 'ExtendedByPolicy'

        # AD: ADCS Attack Paths
        ADCSESC1 = 'ADCSESC1'
        ADCSESC3 = 'ADCSESC3'
        ADCSESC4 = 'ADCSESC4'
        ADCSESC6A = 'ADCSESC6a'
        ADCSESC6B = 'ADCSESC6b'
        ADCSESC9A = 'ADCSESC9a'
        ADCSESC9B = 'ADCSESC9b'
        ADCSESC10A = 'ADCSESC10a'
        ADCSESC10B = 'ADCSESC10b'
        ADCSESC13 = 'ADCSESC13'

        # AD: Azure Sync
        SYNCED_TO_ENTRA_USER = 'SyncedToEntraUser'

        # AD: NTLM Coercion and Relay
        COERCE_AND_RELAY_NTLM_TO_SMB = 'CoerceAndRelayNTLMToSMB'
        COERCE_AND_RELAY_NTLM_TO_ADCS = 'CoerceAndRelayNTLMToADCS'
        COERCE_AND_RELAY_NTLM_TO_LDAP = 'CoerceAndRelayNTLMToLDAP'
        COERCE_AND_RELAY_NTLM_TO_LDAPS = 'CoerceAndRelayNTLMToLDAPS'

        # AD: Limited Rights Variants
        WRITE_OWNER_LIMITED_RIGHTS = 'WriteOwnerLimitedRights'
        WRITE_OWNER_RAW = 'WriteOwnerRaw'
        OWNS_LIMITED_RIGHTS = 'OwnsLimitedRights'
        OWNS_RAW = 'OwnsRaw'

        # AD: Special Identity
        CLAIM_SPECIAL_IDENTITY = 'ClaimSpecialIdentity'

        # AD: Identity and ACE Propagation
        CONTAINS_IDENTITY = 'ContainsIdentity'
        PROPAGATES_ACES_TO = 'PropagatesACEsTo'

        # AD: GPO Application
        GPO_APPLIES_TO = 'GPOAppliesTo'
        CAN_APPLY_GPO = 'CanApplyGPO'

        # AD: Trust Keys
        HAS_TRUST_KEYS = 'HasTrustKeys'

    def __init__(self, label=None, source: 'Optional[Node]' = None, target: 'Optional[Node]' = None,
                 optional: bool = False, length: int = 0, labels: list = None):
        """Create a Relationship.

        Args:
            label: A single Label enum value (backward compatible).
            source: Source node (set when target is the parent).
            target: Target node (set when source is the parent).
            optional: Whether the relationship is optional.
            length: Variable-length path depth (0=single edge, N=1..N, -1=unbounded).
            labels: A list of Label enum values for multi-relationship queries.
        """
        if labels is not None:
            self._labels = labels
        elif label is not None:
            self._labels = [label]
        else:
            self._labels = []
        self.source = source
        self.target = target
        self.optional = optional
        self.length = length

    @property
    def label(self):
        """Return the single label (backward compatible)."""
        return self._labels[0] if self._labels else None

    @label.setter
    def label(self, value):
        self._labels = [value]

    @property
    def labels(self):
        return self._labels

    def to_dict(self):
        if len(self._labels) == 1:
            ret = dict(label=self._labels[0].value)
        elif len(self._labels) > 1:
            ret = dict(label=[label.value for label in self._labels])
        else:
            ret = dict()
        if self.source:
            ret |= dict(source=self.source.to_dict())
        if self.target:
            ret |= dict(target=self.target.to_dict())
        if self.optional:
            ret |= dict(optional=self.optional)
        if self.length:
            ret |= dict(length=self.length)
        return ret


class Node:
    class Label(Enum):
        ASSET = 'Asset'
        REPOSITORY = 'Repository'
        INTEGRATION = 'Integration'
        ADDOMAIN = 'ADDomain'
        ATTRIBUTE = 'Attribute'
        RISK = 'Risk'
        PORT = 'Port'
        PRESEED = 'Preseed'
        SEED = 'Seed'
        TTL = 'TTL'
        WEBAPPLICATION = 'WebApplication'
        WEBPAGE = 'Webpage'

        # Active Directory object types
        ADOBJECT = 'ADObject'
        ADUSER = 'ADUser'
        ADCOMPUTER = 'ADComputer'
        ADGROUP = 'ADGroup'
        ADGPO = 'ADGPO'
        ADOU = 'ADOU'
        ADCONTAINER = 'ADContainer'
        ADLOCALGROUP = 'ADLocalGroup'
        ADLOCALUSER = 'ADLocalUser'
        ADROOTCA = 'ADRootCA'
        ADENTERPRISECA = 'ADEnterpriseCA'
        ADCERTTEMPLATE = 'ADCertTemplate'
        ADNTAUTHSTORE = 'ADNTAuthStore'
        ADAIACA = 'ADAIACA'
        ADISSUANCEPOLICY = 'ADIssuancePolicy'

    def __init__(self, labels: list[Label] = None, filters: list[Filter] = None,
                 relationships: list[Relationship] = None):
        self.labels = labels
        self.filters = filters
        self.relationships = relationships

    def to_dict(self):
        ret = dict()
        if self.labels:
            ret |= dict(labels=[x.value for x in self.labels])
        if self.filters:
            ret |= dict(filters=[x.to_dict() for x in self.filters])
        if self.relationships:
            ret |= dict(relationships=[x.to_dict() for x in self.relationships])
        return ret


class Query:
    def __init__(self, node: Node = None, page: int = 0, limit: int = DEFAULT_PAGE_SIZE, order_by: str = None,
                 descending: bool = False, global_: bool = False, shortest: int = 0):
        self.node = node
        self.page = page
        self.limit = limit
        self.order_by = order_by
        self.descending = descending
        self.global_ = global_
        self.shortest = shortest

    def to_dict(self):
        ret = dict()
        if self.node:
            ret |= dict(node=self.node.to_dict())
        if self.page:
            ret |= dict(page=self.page)
        if self.limit:
            ret |= dict(limit=self.limit)
        if self.order_by:
            ret |= dict(orderBy=self.order_by)
        if self.descending:
            ret |= dict(descending=self.descending)
        if self.shortest:
            ret |= dict(shortest=self.shortest)
        return ret

    def params(self):
        return GLOBAL_FLAG if self.global_ else dict()


# helpers for building graph queries
ASSET_NODE = [Node.Label.ASSET]
RISK_NODE = [Node.Label.RISK]
ATTRIBUTE_NODE = [Node.Label.ATTRIBUTE]
PORT_NODE = [Node.Label.PORT]
WEBAPPLICATION_NODE = [Node.Label.WEBAPPLICATION]
WEBPAGE_NODE = [Node.Label.WEBPAGE]

KIND_TO_LABEL = {
    Kind.ASSET.value: Node.Label.ASSET,
    Kind.RISK.value: Node.Label.RISK,
    Kind.ATTRIBUTE.value: Node.Label.ATTRIBUTE,
    Kind.PORT.value: Node.Label.PORT,
    Kind.SEED.value: Node.Label.SEED,
    Kind.PRESEED.value: Node.Label.PRESEED,
    Kind.REPOSITORY.value: Node.Label.REPOSITORY,
    Kind.INTEGRATION.value: Node.Label.INTEGRATION,
    Kind.ADDOMAIN.value: Node.Label.ADDOMAIN,
    Kind.WEBAPPLICATION.value: Node.Label.WEBAPPLICATION,
    Kind.WEBPAGE.value: Node.Label.WEBPAGE,

    # Active Directory types
    Kind.ADOBJECT.value: Node.Label.ADOBJECT,
    Kind.ADUSER.value: Node.Label.ADUSER,
    Kind.ADCOMPUTER.value: Node.Label.ADCOMPUTER,
    Kind.ADGROUP.value: Node.Label.ADGROUP,
    Kind.ADGPO.value: Node.Label.ADGPO,
    Kind.ADOU.value: Node.Label.ADOU,
    Kind.ADCONTAINER.value: Node.Label.ADCONTAINER,
    Kind.ADLOCALGROUP.value: Node.Label.ADLOCALGROUP,
    Kind.ADLOCALUSER.value: Node.Label.ADLOCALUSER,
    Kind.ADROOTCA.value: Node.Label.ADROOTCA,
    Kind.ADENTERPRISECA.value: Node.Label.ADENTERPRISECA,
    Kind.ADCERTTEMPLATE.value: Node.Label.ADCERTTEMPLATE,
    Kind.ADNTAUTHSTORE.value: Node.Label.ADNTAUTHSTORE,
    Kind.ADAIACA.value: Node.Label.ADAIACA,
    Kind.ADISSUANCEPOLICY.value: Node.Label.ADISSUANCEPOLICY,
}


def key_equals(key: str):
    return [Filter(Filter.Field.KEY, Filter.Operator.EQUAL, key)]


def risk_of_key(key: str):
    return Node(RISK_NODE, filters=key_equals(key))


def asset_of_key(key: str):
    return Node(ASSET_NODE, filters=key_equals(key))


def get_graph_kind(key: str):
    if key and key.startswith('#'):
        split_key = key.split('#')
        if len(split_key) > 1 and split_key[1] in KIND_TO_LABEL:
            return split_key[1]
    return None


def my_params_to_query(params: dict):
    key = params.get('key', None)
    if not key:
        return None

    if key.startswith('#'):
        # this is a key-based search
        kind = get_graph_kind(key)
        if not kind:
            return None

        field = Filter.Field.KEY
        value = key
        if params.get('exact', False):
            operator = Filter.Operator.EQUAL
        else:
            operator = Filter.Operator.STARTS_WITH
    else:
        # this is a "field:value"-style search, such as "source:#asset#exmaple.com#1.2.3.4"
        kind = params.get('label', None)
        if not kind:
            return None

        field = Filter.Field(key.split(':')[0])
        value = key.split(':', 1)[1]
        operator = Filter.Operator.STARTS_WITH

    filter = Filter(field, operator, value)

    label = KIND_TO_LABEL.get(kind, None)
    if not label:
        return None

    node = Node(labels=[label], filters=[filter])

    page = int(params.get('offset', 0))
    global_ = bool(params.get('global', False))

    return Query(node=node, page=page, limit=DEFAULT_PAGE_SIZE, global_=global_)


# AD node label helpers
ADDOMAIN_NODE = [Node.Label.ADDOMAIN]
ADUSER_NODE = [Node.Label.ADUSER]
ADCOMPUTER_NODE = [Node.Label.ADCOMPUTER]
ADGROUP_NODE = [Node.Label.ADGROUP]
ADGPO_NODE = [Node.Label.ADGPO]
ADOU_NODE = [Node.Label.ADOU]
ADCONTAINER_NODE = [Node.Label.ADCONTAINER]
ADOBJECT_NODE = [Node.Label.ADOBJECT]

# Map of AD type name strings to Node.Label lists
AD_TYPE_TO_LABELS = {
    'user': ADUSER_NODE,
    'computer': ADCOMPUTER_NODE,
    'group': ADGROUP_NODE,
    'domain': ADDOMAIN_NODE,
    'gpo': ADGPO_NODE,
    'ou': ADOU_NODE,
    'container': ADCONTAINER_NODE,
    'localgroup': [Node.Label.ADLOCALGROUP],
    'localuser': [Node.Label.ADLOCALUSER],
    'rootca': [Node.Label.ADROOTCA],
    'enterpriseca': [Node.Label.ADENTERPRISECA],
    'certtemplate': [Node.Label.ADCERTTEMPLATE],
    'ntauthstore': [Node.Label.ADNTAUTHSTORE],
    'aiaca': [Node.Label.ADAIACA],
    'issuancepolicy': [Node.Label.ADISSUANCEPOLICY],
}

# Common AD ACL relationship labels for multi-edge traversal
_RL = Relationship.Label
AD_ACL_RELATIONSHIPS = [
    _RL.OWNS, _RL.GENERIC_ALL, _RL.GENERIC_WRITE,
    _RL.WRITE_OWNER, _RL.WRITE_DACL, _RL.FORCE_CHANGE_PASSWORD,
    _RL.ALL_EXTENDED_RIGHTS, _RL.ADD_MEMBER, _RL.ADD_SELF,
    _RL.WRITE_SPN, _RL.ADD_KEY_CREDENTIAL_LINK,
    _RL.ADD_ALLOWED_TO_ACT, _RL.WRITE_ACCOUNT_RESTRICTIONS,
    _RL.READ_LAPS_PASSWORD, _RL.READ_GMSA_PASSWORD,
]

# All AD relationships useful for attack path traversal
AD_ATTACK_PATH_RELATIONSHIPS = [
    *AD_ACL_RELATIONSHIPS,
    _RL.MEMBER_OF, _RL.ADMIN_TO, _RL.CAN_RDP,
    _RL.CAN_PS_REMOTE, _RL.EXECUTE_DCOM, _RL.DCSYNC,
    _RL.ALLOWED_TO_DELEGATE, _RL.ALLOWED_TO_ACT,
    _RL.HAS_SID_HISTORY, _RL.CONTAINS,
    _RL.GPLINK, _RL.SQL_ADMIN,
]

# DCSync-specific relationships
AD_DCSYNC_RELATIONSHIPS = [
    _RL.GET_CHANGES, _RL.GET_CHANGES_ALL,
]
