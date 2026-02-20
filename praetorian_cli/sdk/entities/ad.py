from praetorian_cli.sdk.model.query import (
    Query, Node, Filter, Relationship,
    ADDOMAIN_NODE, ADUSER_NODE, ADCOMPUTER_NODE, ADGROUP_NODE,
    AD_TYPE_TO_LABELS, AD_ACL_RELATIONSHIPS, AD_ATTACK_PATH_RELATIONSHIPS,
    AD_DCSYNC_RELATIONSHIPS, key_equals,
)


class AD:
    """Active Directory graph query entity.

    Methods in this class are accessed from sdk.ad, where sdk is an instance
    of Chariot. Each public method becomes an MCP tool via auto-discovery.
    """

    def __init__(self, api):
        self.api = api

    # ------------------------------------------------------------------
    # Helper: resolve a type string to Node.Label list
    # ------------------------------------------------------------------

    @staticmethod
    def _resolve_type(object_type):
        """Resolve a type name string to a list of Node.Label values."""
        if object_type is None:
            return None
        t = object_type.strip().lower()
        labels = AD_TYPE_TO_LABELS.get(t)
        if labels is None:
            raise ValueError(
                f"Unknown AD object type '{object_type}'. "
                f"Valid types: {', '.join(sorted(AD_TYPE_TO_LABELS.keys()))}"
            )
        return labels

    @staticmethod
    def _resolve_relationship(relationship_type):
        """Resolve a relationship type name to a Relationship.Label."""
        if relationship_type is None:
            return None
        for member in Relationship.Label:
            if member.value.lower() == relationship_type.strip().lower():
                return member
        raise ValueError(
            f"Unknown relationship type '{relationship_type}'. "
            f"Use the exact relationship name, e.g. 'GenericAll', 'MemberOf', 'Owns'."
        )

    @staticmethod
    def _domain_filter(domain):
        """Return a filter for the domain field, or None."""
        if not domain:
            return None
        return Filter(Filter.Field.DOMAIN, Filter.Operator.EQUAL, domain)

    @staticmethod
    def _key_filter(key, prefix=False):
        """Return a filter on the key field."""
        op = Filter.Operator.STARTS_WITH if prefix else Filter.Operator.EQUAL
        return Filter(Filter.Field.KEY, op, key)

    def _run(self, query, pages=1):
        """Execute a query and return (results, offset)."""
        return self.api.search.by_query(query, pages)

    # ------------------------------------------------------------------
    # Public methods (each becomes an MCP tool)
    # ------------------------------------------------------------------

    def list_objects(self, object_type, domain=None, name_contains=None, pages=1):
        """
        List Active Directory objects by type.

        Returns AD objects of the specified type, optionally filtered by domain
        and name substring. Use this to enumerate users, computers, groups, GPOs,
        OUs, and other AD object types.

        :param object_type: AD object type to list (user, computer, group, domain, gpo, ou, container, localgroup, localuser, rootca, enterpriseca, certtemplate, ntauthstore, aiaca, issuancepolicy)
        :type object_type: str
        :param domain: Filter to a specific AD domain (e.g. 'contoso.local')
        :type domain: str
        :param name_contains: Filter objects whose name contains this substring
        :type name_contains: str
        :param pages: Number of result pages to retrieve. <mcp>Start with 1 page unless more are needed.</mcp>
        :type pages: int
        :return: A tuple containing (list of AD objects, next page offset)
        :rtype: tuple
        """
        labels = self._resolve_type(object_type)
        filters = []

        domain_f = self._domain_filter(domain)
        if domain_f:
            filters.append(domain_f)

        if name_contains:
            filters.append(Filter(Filter.Field.NAME, Filter.Operator.CONTAINS, name_contains))

        node = Node(labels=labels, filters=filters or None)
        return self._run(Query(node=node), pages)

    def get_object(self, key=None, objectid=None, domain=None, pages=1):
        """
        Get a specific AD object by key or objectid.

        Retrieves a single AD object. Provide either the full Chariot key
        (e.g. '#aduser#contoso.local#S-1-5-21-...') or the objectid + domain.

        :param key: Full Chariot key of the AD object
        :type key: str
        :param objectid: The AD objectid / SID to look up
        :type objectid: str
        :param domain: AD domain (required when using objectid)
        :type domain: str
        :param pages: Number of result pages. <mcp>Use 1.</mcp>
        :type pages: int
        :return: A tuple containing (list of matching objects, next page offset)
        :rtype: tuple
        """
        if key:
            node = Node(filters=key_equals(key))
            return self._run(Query(node=node), pages)

        if not objectid:
            raise ValueError("Provide either 'key' or 'objectid'")

        filters = [Filter(Filter.Field.OBJECTID, Filter.Operator.EQUAL, objectid)]
        domain_f = self._domain_filter(domain)
        if domain_f:
            filters.append(domain_f)

        node = Node(filters=filters)
        return self._run(Query(node=node), pages)

    def get_relationships(self, source_key=None, target_key=None, relationship_type=None,
                          source_type=None, target_type=None, pages=1):
        """
        Query AD ACL relationships between objects.

        Find relationships of a given type between AD objects. At least one of
        source_key, target_key, or relationship_type should be provided.

        :param source_key: Chariot key of the source AD object
        :type source_key: str
        :param target_key: Chariot key of the target AD object
        :type target_key: str
        :param relationship_type: Relationship type name (e.g. 'GenericAll', 'MemberOf', 'Owns', 'WriteDacl')
        :type relationship_type: str
        :param source_type: AD type of source node (user, computer, group, etc.)
        :type source_type: str
        :param target_type: AD type of target node (user, computer, group, etc.)
        :type target_type: str
        :param pages: Number of result pages. <mcp>Start with 1 page.</mcp>
        :type pages: int
        :return: A tuple containing (list of relationship results, next page offset)
        :rtype: tuple
        """
        rel_label = self._resolve_relationship(relationship_type) if relationship_type else None

        source_labels = self._resolve_type(source_type) if source_type else None
        target_labels = self._resolve_type(target_type) if target_type else None

        source_filters = key_equals(source_key) if source_key else None
        target_filters = key_equals(target_key) if target_key else None

        target_node = Node(labels=target_labels, filters=target_filters)

        rel = Relationship(label=rel_label, target=target_node) if rel_label else \
            Relationship(labels=AD_ACL_RELATIONSHIPS, target=target_node)

        source_node = Node(labels=source_labels, filters=source_filters, relationships=[rel])
        return self._run(Query(node=source_node), pages)

    def find_attack_path(self, source_key, target_key, max_depth=5, shortest=1, pages=1):
        """
        Find shortest attack path between two AD objects.

        Traverses all common AD ACL and privilege escalation edges to find the
        shortest path from source to target. Returns path nodes and relationships.

        :param source_key: Chariot key of the starting AD object
        :type source_key: str
        :param target_key: Chariot key of the destination AD object
        :type target_key: str
        :param max_depth: Maximum path depth / hops (1-10)
        :type max_depth: int
        :param shortest: Number of shortest paths to return (1-10)
        :type shortest: int
        :param pages: Number of result pages. <mcp>Use 1.</mcp>
        :type pages: int
        :return: A tuple containing (list of path results, next page offset)
        :rtype: tuple
        """
        max_depth = int(max_depth)
        shortest = int(shortest)

        target_node = Node(filters=key_equals(target_key))
        rel = Relationship(
            labels=AD_ATTACK_PATH_RELATIONSHIPS,
            target=target_node,
            length=max_depth,
        )
        source_node = Node(filters=key_equals(source_key), relationships=[rel])
        query = Query(node=source_node, shortest=shortest)
        return self._run(query, pages)

    def who_can(self, right, target_key, principal_type=None, pages=1):
        """
        Find all principals that have a specific right over a target AD object.

        For example, find all users/groups that have GenericAll on a domain admin group.

        :param right: The AD right / relationship name (e.g. 'GenericAll', 'WriteDacl', 'Owns', 'ForceChangePassword', 'WriteOwner')
        :type right: str
        :param target_key: Chariot key of the target AD object
        :type target_key: str
        :param principal_type: Filter source principals by type (user, computer, group, etc.)
        :type principal_type: str
        :param pages: Number of result pages. <mcp>Start with 1 page.</mcp>
        :type pages: int
        :return: A tuple containing (list of principals with the right, next page offset)
        :rtype: tuple
        """
        rel_label = self._resolve_relationship(right)
        source_labels = self._resolve_type(principal_type) if principal_type else None
        target_node = Node(filters=key_equals(target_key))

        rel = Relationship(label=rel_label, target=target_node)
        node = Node(labels=source_labels, relationships=[rel])
        return self._run(Query(node=node), pages)

    def what_can(self, source_key, right, target_type=None, pages=1):
        """
        Find what objects a principal has a specific right over.

        For example, find all objects that a compromised user has GenericAll on.

        :param source_key: Chariot key of the source principal
        :type source_key: str
        :param right: The AD right / relationship name (e.g. 'GenericAll', 'WriteDacl', 'Owns')
        :type right: str
        :param target_type: Filter targets by AD type (user, computer, group, etc.)
        :type target_type: str
        :param pages: Number of result pages. <mcp>Start with 1 page.</mcp>
        :type pages: int
        :return: A tuple containing (list of objects the principal has rights over, next page offset)
        :rtype: tuple
        """
        rel_label = self._resolve_relationship(right)
        target_labels = self._resolve_type(target_type) if target_type else None
        source_node = Node(filters=key_equals(source_key))

        rel = Relationship(label=rel_label, source=source_node)
        node = Node(labels=target_labels, relationships=[rel])
        return self._run(Query(node=node), pages)

    def group_members(self, group_key, recursive=False, member_type=None, pages=1):
        """
        List members of an AD group.

        Returns direct members of the group. Set recursive=True to include
        nested group members (transitive MemberOf).

        :param group_key: Chariot key of the AD group
        :type group_key: str
        :param recursive: Include nested/transitive members
        :type recursive: bool
        :param member_type: Filter members by type (user, computer, group, etc.)
        :type member_type: str
        :param pages: Number of result pages. <mcp>Start with 1 page.</mcp>
        :type pages: int
        :return: A tuple containing (list of group members, next page offset)
        :rtype: tuple
        """
        if isinstance(recursive, str):
            recursive = recursive.lower() in ('true', '1', 'yes')

        member_labels = self._resolve_type(member_type) if member_type else None
        group_node = Node(filters=key_equals(group_key))

        length = -1 if recursive else 0
        rel = Relationship(label=Relationship.Label.MEMBER_OF, target=group_node, length=length)
        node = Node(labels=member_labels, relationships=[rel])
        return self._run(Query(node=node), pages)

    def group_memberships(self, object_key, recursive=False, pages=1):
        """
        List all groups an AD object belongs to.

        Returns direct group memberships. Set recursive=True for transitive
        (nested) group memberships.

        :param object_key: Chariot key of the AD object
        :type object_key: str
        :param recursive: Include transitive group memberships
        :type recursive: bool
        :param pages: Number of result pages. <mcp>Start with 1 page.</mcp>
        :type pages: int
        :return: A tuple containing (list of groups, next page offset)
        :rtype: tuple
        """
        if isinstance(recursive, str):
            recursive = recursive.lower() in ('true', '1', 'yes')

        length = -1 if recursive else 0
        group_node = Node(labels=ADGROUP_NODE)
        rel = Relationship(label=Relationship.Label.MEMBER_OF, target=group_node, length=length)
        node = Node(filters=key_equals(object_key), relationships=[rel])
        return self._run(Query(node=node), pages)

    def kerberoastable_users(self, domain=None, pages=1):
        """
        Find Kerberoastable users (users with SPNs set).

        Kerberoastable users have Service Principal Names (SPNs) configured,
        making their TGS tickets requestable and crackable offline.

        :param domain: Filter to a specific AD domain
        :type domain: str
        :param pages: Number of result pages. <mcp>Start with 1 page.</mcp>
        :type pages: int
        :return: A tuple containing (list of kerberoastable users, next page offset)
        :rtype: tuple
        """
        filters = [
            Filter(Filter.Field.HASSPN, Filter.Operator.EQUAL, 'true'),
            Filter(Filter.Field.ENABLED, Filter.Operator.EQUAL, 'true'),
        ]
        domain_f = self._domain_filter(domain)
        if domain_f:
            filters.append(domain_f)

        node = Node(labels=ADUSER_NODE, filters=filters)
        return self._run(Query(node=node), pages)

    def asreproastable_users(self, domain=None, pages=1):
        """
        Find AS-REP roastable users (users without Kerberos pre-authentication).

        These users have 'Do not require Kerberos preauthentication' set,
        allowing offline cracking of their AS-REP encrypted data.

        :param domain: Filter to a specific AD domain
        :type domain: str
        :param pages: Number of result pages. <mcp>Start with 1 page.</mcp>
        :type pages: int
        :return: A tuple containing (list of AS-REP roastable users, next page offset)
        :rtype: tuple
        """
        filters = [
            Filter(Filter.Field.DONTREQPREAUTH, Filter.Operator.EQUAL, 'true'),
            Filter(Filter.Field.ENABLED, Filter.Operator.EQUAL, 'true'),
        ]
        domain_f = self._domain_filter(domain)
        if domain_f:
            filters.append(domain_f)

        node = Node(labels=ADUSER_NODE, filters=filters)
        return self._run(Query(node=node), pages)

    def unconstrained_delegation(self, domain=None, pages=1):
        """
        Find computers with unconstrained delegation enabled.

        Computers with unconstrained delegation cache TGTs of authenticating
        users, which can be extracted for lateral movement.

        :param domain: Filter to a specific AD domain
        :type domain: str
        :param pages: Number of result pages. <mcp>Start with 1 page.</mcp>
        :type pages: int
        :return: A tuple containing (list of unconstrained delegation hosts, next page offset)
        :rtype: tuple
        """
        filters = [
            Filter(Filter.Field.UNCONSTRAINEDDELEGATION, Filter.Operator.EQUAL, 'true'),
            Filter(Filter.Field.ENABLED, Filter.Operator.EQUAL, 'true'),
        ]
        domain_f = self._domain_filter(domain)
        if domain_f:
            filters.append(domain_f)

        node = Node(labels=ADCOMPUTER_NODE, filters=filters)
        return self._run(Query(node=node), pages)

    def dcsync_principals(self, domain_key=None, domain=None, pages=1):
        """
        Find principals that can perform DCSync.

        DCSync allows replication of password hashes from a domain controller.
        This finds principals with both GetChanges and GetChangesAll rights on a
        domain object, or those with the explicit DCSync edge.

        :param domain_key: Chariot key of the AD domain object (e.g. '#addomain#contoso.local#contoso.local')
        :type domain_key: str
        :param domain: AD domain name to filter by (alternative to domain_key)
        :type domain: str
        :param pages: Number of result pages. <mcp>Start with 1 page.</mcp>
        :type pages: int
        :return: A tuple containing (list of DCSync-capable principals, next page offset)
        :rtype: tuple
        """
        target_filters = []
        if domain_key:
            target_filters = key_equals(domain_key)
        elif domain:
            target_filters = [self._domain_filter(domain)]

        target_node = Node(labels=ADDOMAIN_NODE, filters=target_filters or None)
        rel = Relationship(label=Relationship.Label.DCSYNC, target=target_node)
        node = Node(relationships=[rel])
        return self._run(Query(node=node), pages)

    def tier_zero_objects(self, domain=None, pages=1):
        """
        Find tier-zero / high-value AD objects.

        Tier-zero objects include Domain Admins, Enterprise Admins, domain
        controllers, and other objects tagged as high-value in the graph.

        :param domain: Filter to a specific AD domain
        :type domain: str
        :param pages: Number of result pages. <mcp>Start with 1 page.</mcp>
        :type pages: int
        :return: A tuple containing (list of tier-zero objects, next page offset)
        :rtype: tuple
        """
        filters = [
            Filter(Filter.Field.HIGHVALUE, Filter.Operator.EQUAL, 'true'),
        ]
        domain_f = self._domain_filter(domain)
        if domain_f:
            filters.append(domain_f)

        node = Node(filters=filters)
        return self._run(Query(node=node), pages)

    def domains(self, pages=1):
        """
        List all Active Directory domains in the environment.

        Returns all ingested AD domain objects. This is a good starting point
        to discover what AD data is available before running other queries.

        :param pages: Number of result pages. <mcp>Use 1.</mcp>
        :type pages: int
        :return: A tuple containing (list of AD domain objects, next page offset)
        :rtype: tuple
        """
        node = Node(labels=ADDOMAIN_NODE)
        return self._run(Query(node=node), pages)
