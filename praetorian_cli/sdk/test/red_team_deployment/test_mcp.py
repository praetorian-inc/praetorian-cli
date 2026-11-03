"""Deployment tools remain opt-in through actual MCP discovery."""

import anyio
import pytest

from praetorian_cli.sdk.chariot import Chariot
from praetorian_cli.sdk.keychain import Keychain
from praetorian_cli.sdk.mcp_server import MCPServer


@pytest.mark.parametrize('allowlist', [None, ['*'], ['red_team_deployment_*']])
def test_mcp_default_and_wildcard_never_offer_deployment_family(allowlist):
    sdk = Chariot(Keychain(data='[United States]\napi=https://unused.invalid\nclient_id=inert\n'))
    server = MCPServer(sdk, allowable_tools=allowlist)
    listed = anyio.run(server._on_list_tools, None)
    assert not any(tool.name.startswith('red_team_deployment_') for tool in listed.tools)


def test_mcp_exact_inventory_opt_in_does_not_offer_execution():
    sdk = Chariot(Keychain(data='[United States]\napi=https://unused.invalid\nclient_id=inert\n'))
    server = MCPServer(sdk, allowable_tools=['red_team_deployment_inventory'])
    listed = anyio.run(server._on_list_tools, None)
    assert [tool.name for tool in listed.tools] == ['red_team_deployment_inventory']
