from urllib.parse import quote


class Misc:

    def __init__(self, api):
        self.api = api

    def update_technology(self, body):
        return self.api.put('technology', body)

    def create_ticket(self, body):
        return self.api.post('ticket', body)

    def update_ticket(self, body):
        return self.api.put('ticket', body)

    def delete_ticket(self, body):
        return self.api.delete('ticket', body, {})

    def create_monitor(self, body):
        return self.api.post('monitor', body)

    def update_monitor(self, session_id, body):
        return self.api.put('monitor', body, params={'id': session_id})

    def delete_monitor(self, session_id):
        return self.api.delete('monitor', {}, params={'id': session_id})

    def set_flag(self, name):
        return self.api.put('flag', {'name': name})

    def delete_flag(self, name):
        return self.api.delete('flag', {'name': name}, {})

    def create_repository(self, name, source_archive_key):
        return self.api.post('repository', {
            'name': name,
            'source_archive_key': source_archive_key,
        })

    def parse_burp(self, content=None, url=None, filename=None):
        body = {}
        if content:
            body['content'] = content
        if url:
            body['url'] = url
        if filename:
            body['filename'] = filename
        return self.api.post('burp/parse', body)

    def notify_vulnerability(self, body):
        return self.api.post('vulnerability/notify', body)

    def validate_integration(self, body):
        return self.api.post('integration/validate', body)

    def jira_transitions(self, body):
        return self.api.post('integration/jira/transitions', body)

    def jira_custom_fields(self, body):
        return self.api.post('integration/jira/custom-fields', body)

    def jira_optional_custom_fields(self, body):
        return self.api.post('integration/jira/optional-custom-fields', body)

    def jira_priorities(self, body):
        return self.api.post('integration/jira/priorities', body)

    def linear_teams(self, body):
        return self.api.post('integration/linear/teams', body)

    def linear_workflow_states(self, body):
        return self.api.post('integration/linear/workflow-states', body)

    def linear_projects(self, body):
        return self.api.post('integration/linear/projects', body)

    def risk_visited(self, key, comment=''):
        return self.api.put('risk/visited', {'key': key, 'comment': comment})

    def agent_list(self):
        return self.api.get('agent/list')

    def agents(self):
        return self.api.get('agents')

    def planner_compact(self, body):
        return self.api.post('planner/compact', body)

    def planner_stop(self, body):
        return self.api.post('planner/stop', body)

    def planner_interaction(self, body):
        return self.api.post('planner/interaction', body)

    def planner_cost(self, uuid):
        return self.api.get('planner/' + quote(str(uuid), safe='') + '/cost')

    def delete_planner(self, body):
        return self.api.delete('planner', body, {})

    def put_hunt_memory(self, uuid, title, content):
        return self.api.put('hunt/' + quote(str(uuid), safe='') + '/memory/' + quote(str(title), safe=''), {'content': content})

    def delete_hunt_memory(self, uuid, title):
        return self.api.delete('hunt/' + quote(str(uuid), safe='') + '/memory/' + quote(str(title), safe=''), {}, {})

    def hunt_cost(self, uuid):
        return self.api.get('hunt/' + quote(str(uuid), safe='') + '/cost')
