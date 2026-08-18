from urllib.parse import quote


class RedTeam:
    def __init__(self, api):
        self.api = api

    # --- Deployment ---

    def deployment_launch(self, desired_id=None):
        body = {}
        if desired_id:
            body['desired_id'] = desired_id
        return self.api.post('red-team/deployment/launch', body)

    def deployment_delete(self, force=False):
        params = {'force': 'true'} if force else {}
        return self.api.delete('red-team/deployment/delete', {}, params)

    def deployment_details(self):
        return self.api.get('red-team/deployment/details')

    def deployment_history(self):
        return self.api.get('red-team/deployment/history')

    def deployment_last_inputs(self):
        return self.api.get('red-team/deployment/last-inputs')

    def deployment_node_schema(self, tag=None):
        params = {'tag': tag} if tag else {}
        return self.api.get('red-team/deployment/node-schema', params=params)

    def deployment_terraform(self, action, builder_state, tag=None, sha=None):
        params = {}
        if tag:
            params['tag'] = tag
        if sha:
            params['sha'] = sha
        return self.api.post(f'red-team/deployment/terraform/{quote(str(action), safe="")}',
                             builder_state, params=params)

    def deployment_collaborators(self, collaborators):
        return self.api.post('red-team/deployment/collaborators',
                             {'collaborators': collaborators})

    def deployment_tags(self):
        return self.api.get('red-team/deployment/tags')

    # --- Campaigns ---

    def campaign_create(self, campaign):
        return self.api.put('red-team/campaigns', campaign)

    def campaign_delete(self, key):
        return self.api.delete('red-team/campaigns', {'key': key}, {})

    def campaign_targets(self, campaign_id, targets, segment=None):
        body = {'targets': targets}
        if segment:
            body['segment'] = segment
        return self.api.post(f'red-team/campaigns/{quote(str(campaign_id), safe="")}/targets', body)

    def campaign_authorize(self, campaign_id):
        return self.api.post(f'red-team/campaigns/{quote(str(campaign_id), safe="")}/authorize', {})

    def campaign_funnel(self, campaign_id):
        return self.api.get(f'red-team/campaigns/{quote(str(campaign_id), safe="")}/funnel')

    def campaign_activity(self, campaign_id, limit=None):
        params = {'limit': str(limit)} if limit else {}
        return self.api.get(f'red-team/campaigns/{quote(str(campaign_id), safe="")}/activity',
                            params=params)

    # --- Domain parking ---

    def domain_update(self, domain_data):
        return self.api.put('red-team/domain-parking', domain_data)

    def dns_list(self, domain):
        return self.api.get(f'red-team/domain-parking/dns/{quote(str(domain), safe="")}')

    def dns_create(self, domain, record_type, name, content, ttl=1):
        return self.api.post(f'red-team/domain-parking/dns/{quote(str(domain), safe="")}',
                             {'type': record_type, 'name': name,
                              'content': content, 'ttl': ttl})

    def dns_update(self, domain, record_id, record_type, name, content, ttl=1):
        return self.api.put(f'red-team/domain-parking/dns/{quote(str(domain), safe="")}/{quote(str(record_id), safe="")}',
                            {'type': record_type, 'name': name,
                             'content': content, 'ttl': ttl})

    def dns_delete(self, domain, record_id):
        return self.api.delete(
            f'red-team/domain-parking/dns/{quote(str(domain), safe="")}/{quote(str(record_id), safe="")}', {}, {})

    def mailgun_domain_status(self, domain):
        return self.api.get(
            f'red-team/domain-parking/mailgun/domain/{quote(str(domain), safe="")}')

    def mailgun_domain_provision(self, domain):
        return self.api.post(
            f'red-team/domain-parking/mailgun/domain/{quote(str(domain), safe="")}', {})

    def mailgun_domain_delete(self, domain):
        return self.api.delete(
            f'red-team/domain-parking/mailgun/domain/{quote(str(domain), safe="")}', {}, {})

    def mailgun_user_create(self, username, domain):
        return self.api.post('red-team/domain-parking/mailgun/user',
                             {'username': username, 'domain': domain})

    def mailgun_user_delete(self, username, domain):
        return self.api.delete('red-team/domain-parking/mailgun/user',
                               {'username': username, 'domain': domain}, {})

    # --- Evilginx ---

    def evilginx_phishlets(self, node):
        return self.api.get('red-team/evilginx/phishlets',
                            params={'node': node})

    def evilginx_phishlet_params(self, node, name):
        return self.api.get(f'red-team/evilginx/phishlets/{quote(str(name), safe="")}/params',
                            params={'node': node})

    def evilginx_lures(self, node):
        return self.api.get('red-team/evilginx/lures',
                            params={'node': node})

    def evilginx_create_lure(self, node_ref, lure_path):
        return self.api.post('red-team/evilginx/lures',
                             {'node_ref': node_ref, 'lure_path': lure_path})

    def evilginx_configure(self, node_ref, domain, phishlet,
                           phishlet_params=None, unauth_url=None):
        body = {'node_ref': node_ref, 'domain': domain, 'phishlet': phishlet}
        if phishlet_params:
            body['phishlet_params'] = phishlet_params
        if unauth_url:
            body['unauth_url'] = unauth_url
        return self.api.post('red-team/evilginx/configure', body)

    def evilginx_status(self, node):
        return self.api.get('red-team/evilginx/status',
                            params={'node': node})

    # --- Payload & phishkit ---

    def payload_generate(self, shellcode_filename, variables=None):
        body = {'shellcode_s3_filename': shellcode_filename}
        if variables:
            body['variables'] = variables
        return self.api.post('red-team/payload/generate', body)

    def phishkit_nodes(self, status=None):
        params = {'status': status} if status else {}
        return self.api.get('red-team/phishkit-nodes', params=params)
