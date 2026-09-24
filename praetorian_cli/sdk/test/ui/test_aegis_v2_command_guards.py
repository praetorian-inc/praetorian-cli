import pytest

from praetorian_cli.sdk.model.aegis import validate_agent_for_ssh
from praetorian_cli.sdk.test.ui_mocks import MockMenuBase, MockSDK
from praetorian_cli.ui.aegis.commands.cp import handle_cp
from praetorian_cli.ui.aegis.commands.proxy import handle_proxy
from praetorian_cli.ui.aegis.commands.schedule import add_schedule

pytestmark = pytest.mark.tui


class V2Endpoint:
    hostname = "sensor"
    endpoint_id = "endpoint-1"
    version = "v2"

    @property
    def client_id(self):
        raise AssertionError("v2 guards must not inspect legacy client_id")

    @property
    def has_tunnel(self):
        raise AssertionError("v2 guards must not inspect legacy tunnel state")

    @property
    def health_check(self):
        raise AssertionError("v2 guards must not inspect legacy tunnel state")


class Menu(MockMenuBase):
    def __init__(self):
        super().__init__()
        self.sdk = MockSDK()
        self.selected_agent = V2Endpoint()
        self._active_proxies = {}


@pytest.mark.parametrize(
    ("command", "handler", "args"),
    [
        ("cp", handle_cp, ["./local.txt", ":/tmp/remote.txt"]),
        ("proxy", handle_proxy, ["1080"]),
        ("schedule add", lambda menu, _args: add_schedule(menu), []),
    ],
)
def test_v1_only_commands_fail_fast_for_v2_without_legacy_access(command, handler, args):
    menu = Menu()

    handler(menu, args)

    output = "\n".join(menu.console.lines)
    assert f"'{command}' is only supported for Aegis v1 agents" in output
    assert "Selected endpoint is Aegis v2 (endpoint-1)" in output
    assert "Use list or info" in output
    assert menu.sdk.aegis.calls == []
    assert menu.sdk.jobs.calls == []
    assert menu.paused is True


def test_validate_agent_for_ssh_allows_v2_without_legacy_client_id_access():
    class EndpointWithTunnel(V2Endpoint):
        has_tunnel = True

        class _Health:
            class _Cloudflared:
                hostname = 'endpoint.example.com'

            cloudflared_status = _Cloudflared()

        health_check = _Health()

    ok, message = validate_agent_for_ssh(EndpointWithTunnel())

    assert ok is True
    assert message == ''
