import re

from praetorian_cli.sdk.model.globals import Kind
from praetorian_cli.sdk.model.query import Relationship, Node, Query, risk_of_key, ASSET_NODE, PORT_NODE, WEBPAGE_NODE


class Risks:
    """ The methods in this class are to be assessed from sdk.risks, where sdk is an instance
    of Chariot. """

    def __init__(self, api):
        self.api = api

    def add(self, asset_key, name, status, comment=None, capability='', title=None, tags=None):
        """
        Add a risk to an existing asset.

        :param asset_key: The key of an existing asset to associate this risk with
        :type asset_key: str
        :param name: The name of this risk
        :type name: str
        :param status: Risk status from Risk enum (e.g., Risk.TRIAGE_HIGH.value, Risk.OPEN_CRITICAL.value). See globals.py for complete list of valid statuses
        :type status: str
        :param comment: Optional comment for the risk
        :type comment: str or None
        :param capability: Optional capability that discovered this risk
        :type capability: str
        :param title: Optional human-readable title for the risk
        :type title: str or None
        :param tags: Optional tags for the risk
        :type tags: tuple or list or None
        :return: The created risk object
        :rtype: dict
        """
        body = dict(key=asset_key, name=name, status=status, comment=comment, source=capability)
        if title is not None:
            body['title'] = title
        if tags:
            body['tags'] = list(tags)
        return self.api.upsert('risk', body)['risks'][0]

    def get(self, key, details=False):
        """
        Get details of a risk by its exact key.

        :param key: The exact key of a risk (format: #risk#{asset_dns}#{risk_name})
        :type key: str
        :param details: Whether to also retrieve more details about this risk. This will make additional API calls to get the risk attributes and affected assets
        :type details: bool
        :return: The matching risk object or None if not found
        :rtype: dict or None
        """
        risk = self.api.search.by_exact_key(key, details)
        if risk and details:
            risk['affected_assets'] = self.affected_assets(key)
        return risk

    def update(self, key, status=None, comment=None, remove_comment=None, title=None, tags=None):
        """
        Update a risk's status and/or comment, or remove a comment.

        :param key: The key of the risk. If you supply a prefix that matches multiple risks, all of them will be updated
        :type key: str
        :param status: New risk status from Risk enum (e.g., Risk.OPEN_HIGH.value, Risk.REMEDIATED_CRITICAL.value). See globals.py for complete list of valid statuses
        :type status: str or None
        :param comment: Comment for the risk update
        :type comment: str or None
        :param remove_comment: Index of comment to remove (0, 1, ... or -1 for most recent)
        :type remove_comment: int or None
        :param title: Optional human-readable title for the risk
        :type title: str or None
        :param tags: Optional tags for the risk
        :type tags: tuple or list or None
        :return: API response containing update results
        :rtype: dict
        """
        params = dict(key=key)
        if status:
            params = params | dict(status=status)
        if comment:
            params = params | dict(comment=comment)
        if title is not None:
            params['title'] = title
        if tags:
            params['tags'] = list(tags)
        if remove_comment is not None:
            index = self.resolve_comment_entry_index(key, remove_comment)
            params = params | dict(remove=index)

        return self.api.upsert('risk', params)

    def delete(self, key, status, comment=None):
        """
        Delete a risk by setting it to a deleted status.

        :param key: The key of the risk. If you supply a prefix that matches multiple risks, all of them will be deleted
        :type key: str
        :param status: Deletion status from Risk enum (e.g., Risk.DELETED_DUPLICATE_CRITICAL.value, Risk.DELETED_FALSE_POSITIVE_HIGH.value)
        :type status: str
        :param comment: Optional comment for this deletion operation
        :type comment: str or None
        :return: API response containing deletion results
        :rtype: dict
        """
        body = dict(status=status)

        if comment:
            body = body | dict(comment=comment)

        return self.api.delete_by_key('risk', key, body)

    def list(self, contains_filter='', offset=None, pages=100000) -> tuple:
        """
        List risks with optional filtering and pagination.

        :param contains_filter: Filter to apply to the risk key. Ensure the risk's key contains the filter.
        :type contains_filter: str
        :param offset: The offset of the page you want to retrieve results. If not supplied, retrieves from the first page
        :type offset: str or None
        :param pages: The number of pages of results to retrieve. <mcp>Start with one page of results unless specifically requested.</mcp>
        :type pages: int
        :return: A tuple containing (list of matching risks, next page offset)
        :rtype: tuple
        """
        query = Query(
            Node(
                labels=[Node.Label.RISK],
                search=contains_filter if contains_filter else None
            )
        )

        if offset:
            query.page = int(offset)

        return self.api.search.by_query(query, pages)

    def attributes(self, key):
        """
        List attributes associated with a risk.

        :param key: The key of the risk to get attributes for
        :type key: str
        :return: List of attribute objects associated with the risk
        :rtype: list
        """
        attributes, _ = self.api.search.by_source(key, Kind.ATTRIBUTE.value)
        return attributes

    def affected_assets(self, key):
        """
        Get all assets affected by a risk.

        This method finds assets that are directly linked to the risk via HAS_VULNERABILITY
        relationships, as well as assets indirectly linked via ports that have the risk.

        :param key: The key of the risk to get affected assets for
        :type key: str
        :return: List of asset objects affected by the risk (both directly and indirectly linked)
        :rtype: list
        """
        # assets directly linked to the risk
        to_this = Relationship(Relationship.Label.HAS_VULNERABILITY, target=risk_of_key(key))
        query = Query(Node(ASSET_NODE, relationships=[to_this]))
        assets, _ = self.api.search.by_query(query)

        # assets indirectly linked to the risk via a port
        ports = Node(PORT_NODE, relationships=[to_this])
        to_ports = Relationship(Relationship.Label.HAS_PORT, target=ports)
        query = Query(Node(ASSET_NODE, relationships=[to_ports]))
        indirect_assets, _ = self.api.search.by_query(query)

        # webpages linked to the risk
        webpages = Node(WEBPAGE_NODE, relationships=[to_this])
        to_webpages = Relationship(Relationship.Label.HAS_WEBPAGE, target=webpages)
        query = Query(Node(ASSET_NODE, relationships=[to_webpages]))
        web_assets, _ = self.api.search.by_query(query)

        assets.extend(indirect_assets)
        assets.extend(web_assets)
        return assets

    def resolve_comment_entry_index(self, key, note_index):
        """
        Translate a note index to the actual history array index.

        :param key: The key of the risk
        :param note_index: Index into note entries (0, 1, ... or -1 for most recent note)
        :return: The actual index in the history array
        """
        risk = self.get(key)
        history = risk.get('history', [])
        note_indices = get_note_entry_indices(history)

        if len(note_indices) == 0:
            raise Exception(f"Risk {key} has no notes to remove")

        # Handle negative indexing (e.g., -1 for last note)
        if note_index < 0:
            note_index = len(note_indices) + note_index

        if note_index < 0 or note_index >= len(note_indices):
            raise Exception(f"Note index {note_index} is out of range (0 to {len(note_indices) - 1})")

        return note_indices[note_index]

    def hydrate_evidence(self, key):
        """
        Fetch all evidence associated with a risk from all sources: attributes, webpages,
        files, and definitions. Returns a normalized dict with the risk record, parsed
        definition, evidence items, and affected assets.

        :param key: The key of the risk
        :type key: str
        :return: A dict with keys: risk, definition, evidence, affected_assets
        :rtype: dict
        """
        # 1. Get the risk record with details (attributes + affected_assets)
        risk_record = self.get(key, details=True)

        # 2. Fetch attributes associated with the risk
        attributes, _ = self.api.search.by_source(key, Kind.ATTRIBUTE.value)

        # 3. Fetch webpages associated with the risk
        webpages, _ = self.api.search.by_source(key, Kind.WEBPAGE.value)

        # 4. Try to fetch the risk definition
        # Extract the risk name from the key (format: #risk#{asset_dns}#{risk_name})
        parts = key.split('#')
        risk_name = parts[-1] if parts else key

        definition = None
        try:
            # Try account-level definition first
            raw_definition = self.api.files.get_utf8(f'definitions/{risk_name}')
            definition = self._parse_definition(raw_definition)
        except Exception:
            try:
                # Fall back to global definition
                raw_definition = self.api.files.get_utf8(f'definitions/{risk_name}', _global=True)
                definition = self._parse_definition(raw_definition)
            except Exception:
                definition = None

        # 5. Build evidence list
        evidence = []
        for attr in attributes:
            evidence.append({
                'source': 'attribute',
                'name': attr.get('name', ''),
                'value': attr.get('value', ''),
            })
        for wp in webpages:
            evidence.append({
                'source': 'webpage',
                'url': wp.get('name', ''),
                'content': wp.get('value', ''),
            })

        # 6. Get affected assets from the risk record (already fetched via details=True)
        affected_assets = risk_record.get('affected_assets', []) if risk_record else []

        return {
            'risk': risk_record,
            'definition': definition,
            'evidence': evidence,
            'affected_assets': affected_assets,
        }

    @staticmethod
    def _parse_definition(raw_markdown):
        """
        Parse a definition markdown string and extract known sections:
        Description, Impact, Recommendation, References.

        :param raw_markdown: The raw markdown text of the definition
        :type raw_markdown: str
        :return: A dict with keys: description, impact, recommendation, references, raw
        :rtype: dict
        """
        sections = {
            'description': '',
            'impact': '',
            'recommendation': '',
            'references': [],
            'raw': raw_markdown,
        }

        # Split on ## headers
        parts = re.split(r'^##\s+', raw_markdown, flags=re.MULTILINE)

        for part in parts:
            lines = part.strip().split('\n', 1)
            if len(lines) < 1:
                continue
            header = lines[0].strip().lower()
            body = lines[1].strip() if len(lines) > 1 else ''

            if header == 'description':
                sections['description'] = body
            elif header == 'impact':
                sections['impact'] = body
            elif header == 'recommendation':
                sections['recommendation'] = body
            elif header == 'references':
                # Parse references as a list of non-empty lines
                refs = [line.strip().lstrip('- ').strip() for line in body.split('\n') if line.strip()]
                sections['references'] = refs

        return sections


def get_note_entries(risk):
    history = risk.get('history', [])
    return [entry for entry in history if is_note_entry(entry)]


def get_note_entry_indices(history):
    """Return the indices in the history array that are note entries."""
    return [i for i, entry in enumerate(history) if is_note_entry(entry)]


def is_note_entry(entry):
    return entry.get('comment') is not None