class Aegis:

    def __init__(self, api):
        self.api = api

    def list(self, offset=None, pages=100000) -> tuple:
        """ List Aegis agents """
        try:
            # Aegis agents use a different API endpoint
            resp = self.api._make_request('GET', self.api.url('/aegis/agent'))
            if resp.status_code != 200:
                return [], None
            agents_data = resp.json()
            
            # Transform the agent data to match the expected format with 'key' field
            formatted_agents = []
            for agent in agents_data:
                formatted_agent = {
                    'key': f"#aegis-agent#{agent.get('client_id', 'unknown')}#{agent.get('hostname', 'unknown')}",
                    'client_id': agent.get('client_id'),
                    'hostname': agent.get('hostname'),
                    'fqdn': agent.get('fqdn'),
                    'os': agent.get('os'),
                    'os_version': agent.get('os_version'),
                    'architecture': agent.get('architecture'),
                    'last_seen_at': agent.get('last_seen_at'),
                    'network_interfaces': agent.get('network_interfaces', []),
                    'health_check': agent.get('health_check')
                }
                formatted_agents.append(formatted_agent)
            
            return formatted_agents, None
        except Exception as e:
            # Fallback to the standard key-based search if the endpoint doesn't exist
            return self.api.search.by_key_prefix('#agent#', offset, pages)
    
    def get_by_client_id(self, client_id: str) -> dict:
        """ Get a specific Aegis agent by client_id """
        try:
            agents_data, _ = self.list()
            for agent in agents_data:
                if agent.get('client_id') == client_id:
                    return agent
            return None
        except Exception as e:
            raise Exception(f"Failed to get agent {client_id}: {e}")