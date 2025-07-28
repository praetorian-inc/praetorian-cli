from time import sleep, time
import asyncio

from praetorian_cli.sdk.model.globals import AgentType
from praetorian_cli.sdk.mcp_server import MCPServer


class Agents:

    def __init__(self, api):
        self.api = api

    def affiliation(self, key, timeout=180) -> str:
        self.api.agent(AgentType.AFFILIATION.value, dict(key=key))

        # poll for the affiliation job to complete
        job_key = self.api.jobs.system_job_key(AgentType.AFFILIATION.value, key)

        start_time = time()
        while time() - start_time < timeout:
            job = self.api.jobs.get(job_key)
            if self.api.jobs.is_failed(job):
                raise Exception('Failed to retrieve affiliation data.')
            if self.api.jobs.is_passed(job):
                break
            sleep(1)

        if self.api.jobs.is_passed(job):
            return self.affiliation_result(key)
        else:
            raise Exception(f'Timeout waiting for affiliation result ({timeout} seconds).')

    def affiliation_filename(self, agent_type: str, key: str) -> str:
        return f'agents/{agent_type}/{key}'

    def affiliation_result(self, key: str) -> dict:
        return self.api.files.get_utf8(self.affiliation_filename(AgentType.AFFILIATION.value, key))

    def start_mcp_server(self, allowable_tools=None):
        server = MCPServer(self.api, allowable_tools)
        return asyncio.run(server.start())

    def list_mcp_tools(self, allowable_tools=None):
        server = MCPServer(self.api, allowable_tools)
        return server.discovered_tools
