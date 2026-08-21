from urllib.parse import quote

# The terraform sub-steps this client is allowed to drive. `generate`, `outputs`
# and `tag` are backend-only sub-steps of the deployment pipeline and are
# deliberately NOT reachable from the CLI, the SDK, or the MCP surface.
TERRAFORM_ACTIONS = ('plan', 'apply')


def _segment(value):
    """Encode one URL path segment, rejecting values that would redirect the route.

    `quote` leaves dot-segments intact and `requests` normalizes them away before
    transmission, so `..` as a segment silently retargets the request at the parent
    route. Validate, then encode.
    """
    text = str(value)
    if not text or text in ('.', '..'):
        raise ValueError(f'invalid URL path segment: {value!r}')
    return quote(text, safe='')


class RedTeam:
    """
    Manage Red Team phishing infrastructure, campaigns, and payloads.

    This class provides methods to drive the Red Team deployment lifecycle,
    phishing campaigns, parked domains and their DNS, Mailgun mail delivery,
    Evilginx phishing proxies, and payload generation. All operations are
    restricted to Praetorian engineers only and require appropriate
    authentication.

    Red Team operations are accessed from sdk.red_team, where sdk is an
    instance of Chariot.

    Example:
        >>> chariot = Chariot()
        >>> chariot.red_team.deployment_launch()
        >>> chariot.red_team.campaign_funnel('camp-1')
    """

    def __init__(self, api):
        self.api = api

    def _check_if_praetorian(self):
        if not self.api.is_praetorian_user():
            raise RuntimeError(
                "This option is limited to Praetorian engineers only. "
                "Please contact your Praetorian representative for assistance."
            )

    # --- Deployment ---

    def deployment_launch(self, desired_id=None):
        """
        Launch a new Red Team deployment.

        Provisions the Red Team infrastructure deployment for the current
        account. At most one deployment exists per account.

        :param desired_id: The deployment ID to request, or None to let the
                           backend assign one
        :type desired_id: str or None
        :return: The launched deployment record
        :rtype: dict
        :raises RuntimeError: If the user is not a Praetorian engineer
        """
        self._check_if_praetorian()
        body = {}
        if desired_id:
            body['desired_id'] = desired_id
        return self.api.post('red-team/deployment/launch', body)

    def deployment_delete(self, force=False):
        """
        Destructively delete the Red Team deployment and all its infrastructure.

        This action is irreversible. Every node, phishing proxy, and piece of
        provisioned infrastructure in the deployment is torn down.

        :param force: Whether to force deletion even when the backend reports
                      the deployment is not in a deletable state
        :type force: bool
        :return: Result of the delete operation
        :rtype: dict
        :raises RuntimeError: If the user is not a Praetorian engineer
        """
        self._check_if_praetorian()
        params = {'force': 'true'} if force else {}
        return self.api.delete('red-team/deployment/delete', {}, params)

    def deployment_details(self):
        """
        Get the current Red Team deployment details.

        Retrieves the deployment record for the current account, including its
        nodes and their provisioning state.

        :return: The current deployment details
        :rtype: dict
        :raises RuntimeError: If the user is not a Praetorian engineer
        """
        self._check_if_praetorian()
        return self.api.get('red-team/deployment/details')

    def deployment_history(self):
        """
        Get the Red Team deployment action history.

        Retrieves the audit trail of deployment actions (launches, plans,
        applies, deletions) for the current account.

        :return: The list of historical deployment actions
        :rtype: list
        :raises RuntimeError: If the user is not a Praetorian engineer
        """
        self._check_if_praetorian()
        return self.api.get('red-team/deployment/history')

    def deployment_last_inputs(self):
        """
        Get the last submitted builder configuration.

        Retrieves the most recent builder state that was submitted for a
        terraform plan or apply, suitable for re-submission after editing.

        :return: The last submitted builder state
        :rtype: dict
        :raises RuntimeError: If the user is not a Praetorian engineer
        """
        self._check_if_praetorian()
        return self.api.get('red-team/deployment/last-inputs')

    def deployment_node_schema(self, tag=None):
        """
        Get the node catalog schema for Red Team infrastructure.

        Retrieves the catalog of node types and their configurable parameters,
        which describes the shape of a valid builder state.

        :param tag: The infrastructure version tag to read the schema for, or
                    None for the default version
        :type tag: str or None
        :return: The node catalog schema
        :rtype: dict
        :raises RuntimeError: If the user is not a Praetorian engineer
        """
        self._check_if_praetorian()
        params = {'tag': tag} if tag else {}
        return self.api.get('red-team/deployment/node-schema', params=params)

    def deployment_terraform(self, action, builder_state, tag=None, sha=None):
        """
        Run a terraform plan or apply against a builder state.

        The 'apply' action mutates live infrastructure and is irreversible in
        the sense that it provisions, reconfigures, or destroys nodes to match
        the submitted builder state. Only 'plan' and 'apply' are reachable from
        this client; the remaining backend-only sub-steps are not exposed.

        :param action: The terraform action to run, either 'plan' or 'apply'
        :type action: str
        :param builder_state: The builder state document sent as the request
                              body, describing the desired infrastructure
        :type builder_state: dict
        :param tag: The infrastructure version tag to run against, or None for
                    the default version
        :type tag: str or None
        :param sha: The git commit SHA to run against, or None for the default
        :type sha: str or None
        :return: The queued terraform job record
        :rtype: dict
        :raises ValueError: If action is not 'plan' or 'apply'
        :raises RuntimeError: If the user is not a Praetorian engineer
        """
        self._check_if_praetorian()
        if action not in TERRAFORM_ACTIONS:
            raise ValueError(
                f'invalid terraform action: {action!r}; '
                f'expected one of {", ".join(repr(a) for a in TERRAFORM_ACTIONS)}'
            )
        params = {}
        if tag:
            params['tag'] = tag
        if sha:
            params['sha'] = sha
        return self.api.post(f'red-team/deployment/terraform/{_segment(action)}',
                             builder_state, params=params)

    def deployment_collaborators(self, collaborators):
        """
        Replace the collaborator list on the Red Team deployment.

        The submitted list replaces the existing collaborators, so any address
        omitted from it loses access to the deployment.

        :param collaborators: The email addresses to grant deployment access to
        :type collaborators: list
        :return: The updated collaborator list
        :rtype: list
        :raises RuntimeError: If the user is not a Praetorian engineer
        """
        self._check_if_praetorian()
        return self.api.post('red-team/deployment/collaborators',
                             {'collaborators': collaborators})

    def deployment_tags(self):
        """
        List the available Red Team infrastructure version tags.

        Retrieves the infrastructure versions that can be passed as the `tag`
        argument to the node-schema and terraform operations.

        :return: The list of available version tags
        :rtype: list
        :raises RuntimeError: If the user is not a Praetorian engineer
        """
        self._check_if_praetorian()
        return self.api.get('red-team/deployment/tags')

    # --- Campaigns ---

    def campaign_create(self, campaign):
        """
        Create or update a phishing campaign.

        Upserts the campaign record. A campaign created here is not live until
        it is explicitly authorized.

        :param campaign: The campaign document sent as the request body
        :type campaign: dict
        :return: The created or updated campaign
        :rtype: dict
        :raises RuntimeError: If the user is not a Praetorian engineer
        """
        self._check_if_praetorian()
        return self.api.put('red-team/campaigns', campaign)

    def campaign_delete(self, key):
        """
        Destructively delete a phishing campaign.

        This action is irreversible. The campaign and its recorded activity are
        removed.

        :param key: The exact key of the campaign to delete
                    (e.g., '#campaign#my-campaign')
        :type key: str
        :return: Result of the delete operation
        :rtype: dict
        :raises RuntimeError: If the user is not a Praetorian engineer
        """
        self._check_if_praetorian()
        return self.api.delete('red-team/campaigns', {'key': key}, {})

    def campaign_targets(self, campaign_id, targets, segment=None):
        """
        Replace the full target roster of a campaign, discarding the previous one.

        The submitted list replaces every target currently on the campaign, so
        any recipient omitted from it is removed.

        :param campaign_id: The ID of the campaign to set targets on
        :type campaign_id: str
        :param targets: The target recipient records that make up the new roster
        :type targets: list
        :param segment: The target segment name to assign, or None for the
                        default segment
        :type segment: str or None
        :return: The stored target roster
        :rtype: list
        :raises ValueError: If campaign_id is not a usable URL path segment
        :raises RuntimeError: If the user is not a Praetorian engineer
        """
        self._check_if_praetorian()
        body = {'targets': targets}
        if segment:
            body['segment'] = segment
        return self.api.post(f'red-team/campaigns/{_segment(campaign_id)}/targets', body)

    def campaign_authorize(self, campaign_id):
        """
        Authorize a campaign to go live, sending phishing email to real recipients.

        This is the highest-consequence Red Team operation: once authorized, the
        campaign begins delivering live phishing email to every target on its
        roster.

        :param campaign_id: The ID of the campaign to authorize
        :type campaign_id: str
        :return: The authorization result, including the campaign's live status
        :rtype: dict
        :raises ValueError: If campaign_id is not a usable URL path segment
        :raises RuntimeError: If the user is not a Praetorian engineer
        """
        self._check_if_praetorian()
        return self.api.post(f'red-team/campaigns/{_segment(campaign_id)}/authorize', {})

    def campaign_funnel(self, campaign_id):
        """
        Get the delivery and engagement funnel metrics for a campaign.

        Retrieves aggregate counts across the campaign funnel (sent, opened,
        clicked, submitted).

        :param campaign_id: The ID of the campaign to read metrics for
        :type campaign_id: str
        :return: The campaign funnel metrics
        :rtype: dict
        :raises ValueError: If campaign_id is not a usable URL path segment
        :raises RuntimeError: If the user is not a Praetorian engineer
        """
        self._check_if_praetorian()
        return self.api.get(f'red-team/campaigns/{_segment(campaign_id)}/funnel')

    def campaign_activity(self, campaign_id, limit=None):
        """
        Get the recorded activity events for a campaign.

        Retrieves the per-recipient event stream for the campaign (deliveries,
        opens, clicks, credential submissions).

        :param campaign_id: The ID of the campaign to read activity for
        :type campaign_id: str
        :param limit: The maximum number of events to return, or None to let the
                      backend choose
        :type limit: int
        :return: The list of activity events
        :rtype: list
        :raises ValueError: If campaign_id is not a usable URL path segment
        :raises RuntimeError: If the user is not a Praetorian engineer
        """
        self._check_if_praetorian()
        params = {'limit': str(limit)} if limit else {}
        return self.api.get(f'red-team/campaigns/{_segment(campaign_id)}/activity',
                            params=params)

    # --- Domain parking ---

    def domain_update(self, domain_data):
        """
        Update a parked domain record.

        Upserts the parked-domain record, which controls how the domain is
        allocated to engagements and phishing infrastructure.

        :param domain_data: The parked domain document sent as the request body
        :type domain_data: dict
        :return: The updated parked domain record
        :rtype: dict
        :raises RuntimeError: If the user is not a Praetorian engineer
        """
        self._check_if_praetorian()
        return self.api.put('red-team/domain-parking', domain_data)

    def dns_list(self, domain):
        """
        List the DNS records of a parked domain.

        Retrieves every DNS record currently configured at the DNS provider for
        the parked domain.

        :param domain: The parked domain name to list records for
        :type domain: str
        :return: The DNS records of the domain
        :rtype: dict
        :raises ValueError: If domain is not a usable URL path segment
        :raises RuntimeError: If the user is not a Praetorian engineer
        """
        self._check_if_praetorian()
        return self.api.get(f'red-team/domain-parking/dns/{_segment(domain)}')

    def dns_create(self, domain, record_type, name, content, ttl=1):
        """
        Create a DNS record on a parked domain.

        Adds a record at the DNS provider. This changes live DNS resolution for
        the domain.

        :param domain: The parked domain name to add the record to
        :type domain: str
        :param record_type: The DNS record type ('A', 'CNAME', 'MX', 'TXT')
        :type record_type: str
        :param name: The record name (the host portion, e.g., 'www')
        :type name: str
        :param content: The record value (e.g., an IP address or target host)
        :type content: str
        :param ttl: The record time-to-live in seconds; 1 means automatic
        :type ttl: int
        :return: The created DNS record
        :rtype: dict
        :raises ValueError: If domain is not a usable URL path segment
        :raises RuntimeError: If the user is not a Praetorian engineer
        """
        self._check_if_praetorian()
        return self.api.post(f'red-team/domain-parking/dns/{_segment(domain)}',
                             {'type': record_type, 'name': name,
                              'content': content, 'ttl': ttl})

    def dns_update(self, domain, record_id, record_type, name, content, ttl=1):
        """
        Overwrite an existing DNS record on a parked domain.

        The submitted values replace the record's current type, name, content
        and TTL, changing live DNS resolution for the domain.

        :param domain: The parked domain name that owns the record
        :type domain: str
        :param record_id: The ID of the DNS record to overwrite
        :type record_id: str
        :param record_type: The DNS record type ('A', 'CNAME', 'MX', 'TXT')
        :type record_type: str
        :param name: The record name (the host portion, e.g., 'www')
        :type name: str
        :param content: The record value (e.g., an IP address or target host)
        :type content: str
        :param ttl: The record time-to-live in seconds; 1 means automatic
        :type ttl: int
        :return: The updated DNS record
        :rtype: dict
        :raises ValueError: If domain or record_id is not a usable URL path
                            segment
        :raises RuntimeError: If the user is not a Praetorian engineer
        """
        self._check_if_praetorian()
        return self.api.put(
            f'red-team/domain-parking/dns/{_segment(domain)}/{_segment(record_id)}',
            {'type': record_type, 'name': name,
             'content': content, 'ttl': ttl})

    def dns_delete(self, domain, record_id):
        """
        Destructively delete a DNS record from a parked domain.

        This action is irreversible and changes live DNS resolution for the
        domain immediately.

        :param domain: The parked domain name that owns the record
        :type domain: str
        :param record_id: The ID of the DNS record to delete
        :type record_id: str
        :return: Result of the delete operation
        :rtype: dict
        :raises ValueError: If domain or record_id is not a usable URL path
                            segment
        :raises RuntimeError: If the user is not a Praetorian engineer
        """
        self._check_if_praetorian()
        return self.api.delete(
            f'red-team/domain-parking/dns/{_segment(domain)}/{_segment(record_id)}',
            {}, {})

    def mailgun_domain_status(self, domain):
        """
        Get the Mailgun provisioning status of a parked domain.

        Retrieves the mail-delivery state of the domain at Mailgun, including
        its DNS verification records.

        :param domain: The parked domain name to read Mailgun status for
        :type domain: str
        :return: The Mailgun domain status
        :rtype: dict
        :raises ValueError: If domain is not a usable URL path segment
        :raises RuntimeError: If the user is not a Praetorian engineer
        """
        self._check_if_praetorian()
        return self.api.get(
            f'red-team/domain-parking/mailgun/domain/{_segment(domain)}')

    def mailgun_domain_provision(self, domain):
        """
        Provision a parked domain for mail delivery at Mailgun.

        Registers the domain at Mailgun and issues the sending credentials that
        phishing campaigns deliver through.

        :param domain: The parked domain name to provision
        :type domain: str
        :return: The provisioned Mailgun domain record
        :rtype: dict
        :raises ValueError: If domain is not a usable URL path segment
        :raises RuntimeError: If the user is not a Praetorian engineer
        """
        self._check_if_praetorian()
        return self.api.post(
            f'red-team/domain-parking/mailgun/domain/{_segment(domain)}', {})

    def mailgun_domain_delete(self, domain):
        """
        Destructively delete a Mailgun domain and its sending credentials.

        This action is irreversible. Campaigns that deliver through the domain
        stop being able to send mail.

        :param domain: The parked domain name to delete at Mailgun
        :type domain: str
        :return: Result of the delete operation
        :rtype: dict
        :raises ValueError: If domain is not a usable URL path segment
        :raises RuntimeError: If the user is not a Praetorian engineer
        """
        self._check_if_praetorian()
        return self.api.delete(
            f'red-team/domain-parking/mailgun/domain/{_segment(domain)}', {}, {})

    def mailgun_user_create(self, username, domain):
        """
        Create a Mailgun SMTP user and its sending credential.

        Issues an SMTP credential on the domain, which campaigns use to send
        phishing email.

        :param username: The SMTP username to create
        :type username: str
        :param domain: The Mailgun domain to create the user on
        :type domain: str
        :return: The created SMTP user, including its credential
        :rtype: dict
        :raises RuntimeError: If the user is not a Praetorian engineer
        """
        self._check_if_praetorian()
        return self.api.post('red-team/domain-parking/mailgun/user',
                             {'username': username, 'domain': domain})

    def mailgun_user_delete(self, username, domain):
        """
        Destructively delete a Mailgun SMTP user and revoke its credential.

        This action is irreversible. Anything sending as that SMTP user stops
        being able to deliver mail.

        :param username: The SMTP username to delete
        :type username: str
        :param domain: The Mailgun domain that owns the user
        :type domain: str
        :return: Result of the delete operation
        :rtype: dict
        :raises RuntimeError: If the user is not a Praetorian engineer
        """
        self._check_if_praetorian()
        return self.api.delete('red-team/domain-parking/mailgun/user',
                               {'username': username, 'domain': domain}, {})

    # --- Evilginx ---

    def evilginx_phishlets(self, node):
        """
        List the Evilginx phishlets available on a phishkit node.

        Retrieves the phishlet definitions the node can be configured with.

        :param node: The phishkit node reference to query
        :type node: str
        :return: The available phishlets
        :rtype: dict
        :raises RuntimeError: If the user is not a Praetorian engineer
        """
        self._check_if_praetorian()
        return self.api.get('red-team/evilginx/phishlets',
                            params={'node': node})

    def evilginx_phishlet_params(self, node, name):
        """
        Get the configurable parameters of a specific Evilginx phishlet.

        Retrieves the parameter names a phishlet expects, which are supplied
        when configuring Evilginx on a node.

        :param node: The phishkit node reference to query
        :type node: str
        :param name: The phishlet name to read parameters for (e.g., 'o365')
        :type name: str
        :return: The phishlet parameters
        :rtype: dict
        :raises ValueError: If name is not a usable URL path segment
        :raises RuntimeError: If the user is not a Praetorian engineer
        """
        self._check_if_praetorian()
        return self.api.get(f'red-team/evilginx/phishlets/{_segment(name)}/params',
                            params={'node': node})

    def evilginx_lures(self, node):
        """
        List the Evilginx lures configured on a phishkit node.

        Retrieves the lure URLs that route visitors into the phishing proxy.

        :param node: The phishkit node reference to query
        :type node: str
        :return: The configured lures
        :rtype: dict
        :raises RuntimeError: If the user is not a Praetorian engineer
        """
        self._check_if_praetorian()
        return self.api.get('red-team/evilginx/lures',
                            params={'node': node})

    def evilginx_create_lure(self, node_ref, lure_path):
        """
        Create an Evilginx lure on a phishkit node.

        Publishes a live lure URL on the node's phishing proxy at the given
        path.

        :param node_ref: The phishkit node reference to create the lure on
        :type node_ref: str
        :param lure_path: The URL path the lure is served at (e.g., '/login')
        :type lure_path: str
        :return: The queued lure-creation job record
        :rtype: dict
        :raises RuntimeError: If the user is not a Praetorian engineer
        """
        self._check_if_praetorian()
        return self.api.post('red-team/evilginx/lures',
                             {'node_ref': node_ref, 'lure_path': lure_path})

    def evilginx_configure(self, node_ref, domain, phishlet,
                           phishlet_params=None, unauth_url=None):
        """
        Overwrite the Evilginx phishing configuration on a phishkit node.

        The submitted values replace the node's current phishing proxy
        configuration, changing which domain and phishlet it serves live.

        :param node_ref: The phishkit node reference to configure
        :type node_ref: str
        :param domain: The domain the phishing proxy serves
        :type domain: str
        :param phishlet: The phishlet name to activate (e.g., 'o365')
        :type phishlet: str
        :param phishlet_params: The phishlet parameter values, or None to leave
                                them unset
        :type phishlet_params: dict
        :param unauth_url: The URL unauthenticated visitors are redirected to,
                           or None for the default
        :type unauth_url: str or None
        :return: The queued configuration job record
        :rtype: dict
        :raises RuntimeError: If the user is not a Praetorian engineer
        """
        self._check_if_praetorian()
        body = {'node_ref': node_ref, 'domain': domain, 'phishlet': phishlet}
        if phishlet_params is not None:
            body['phishlet_params'] = phishlet_params
        if unauth_url:
            body['unauth_url'] = unauth_url
        return self.api.post('red-team/evilginx/configure', body)

    def evilginx_status(self, node):
        """
        Get the Evilginx configuration status of a phishkit node.

        Retrieves whether the node's phishing proxy is configured and ready to
        receive traffic.

        :param node: The phishkit node reference to query
        :type node: str
        :return: The Evilginx status of the node
        :rtype: dict
        :raises RuntimeError: If the user is not a Praetorian engineer
        """
        self._check_if_praetorian()
        return self.api.get('red-team/evilginx/status',
                            params={'node': node})

    # --- Payload & phishkit ---

    def payload_generate(self, shellcode_filename, variables=None):
        """
        Generate an executable payload that embeds uploaded shellcode.

        Builds a payload artifact around the named shellcode file, applying the
        supplied template variables.

        :param shellcode_filename: The S3 filename of the uploaded shellcode to
                                   embed
        :type shellcode_filename: str
        :param variables: The payload template variable values, or None to use
                          the defaults
        :type variables: dict
        :return: The queued payload-generation job record
        :rtype: dict
        :raises RuntimeError: If the user is not a Praetorian engineer
        """
        self._check_if_praetorian()
        body = {'shellcode_s3_filename': shellcode_filename}
        if variables is not None:
            body['variables'] = variables
        return self.api.post('red-team/payload/generate', body)

    def phishkit_nodes(self, status=None):
        """
        List the phishkit nodes of the Red Team deployment.

        Retrieves the nodes that host phishing proxies and lures, optionally
        filtered by their run state.

        :param status: The node status to filter by (e.g., 'running', 'all'), or
                       None for the backend default
        :type status: str or None
        :return: The list of phishkit nodes
        :rtype: list
        :raises RuntimeError: If the user is not a Praetorian engineer
        """
        self._check_if_praetorian()
        params = {'status': status} if status else {}
        return self.api.get('red-team/phishkit-nodes', params=params)
