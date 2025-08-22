class MockConsole:
    def __init__(self):
        self.lines = []

    def print(self, msg=""):
        self.lines.append(str(msg))


class MockAegis:
    def __init__(self, responses=None):
        self.calls = []
        self._responses = responses or {}

    def ssh_to_agent(self, agent, options, user, display_info=True):
        self.calls.append({
            'method': 'ssh_to_agent',
            'agent': agent,
            'options': list(options),
            'user': user,
            'display_info': display_info,
        })

    def run_job(self, agent, capabilities=None, config=None):
        self.calls.append({
            'method': 'run_job',
            'agent': agent,
            'capabilities': capabilities,
            'config': config,
        })
        if capabilities is None:
            return self._responses.get('list_caps', {'capabilities': []})
        return self._responses.get('run', {'success': True, 'job_id': 'abc123', 'job_key': 'k', 'status': 'queued'})


class MockSDK:
    def __init__(self, responses=None):
        self.aegis = MockAegis(responses=responses)


class MockAgent:
    def __init__(self, hostname="agent01", client_id="C.1"):
        self.hostname = hostname
        self.client_id = client_id

    def to_detailed_string(self):
        return f"Agent {self.hostname} ({self.client_id})"


class MockMenuBase:
    def __init__(self):
        self.console = MockConsole()
        self.paused = False

    def pause(self):
        self.paused = True

