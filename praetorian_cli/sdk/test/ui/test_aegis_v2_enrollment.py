from unittest.mock import patch

import pytest
from rich.console import Console

from praetorian_cli.sdk.test.test_aegis_v2_enrollment import PENDING_RAW
from praetorian_cli.sdk.test.ui_mocks import MockMenuBase, MockSDK
from praetorian_cli.ui.aegis.commands.enrollment import handle_enrollment

pytestmark = pytest.mark.tui


class Menu(MockMenuBase):
    def __init__(self, responses=None):
        super().__init__()
        self.sdk = MockSDK(responses=responses)
        self.commands = ['enrollment']


def test_tui_enrollment_inspect_shows_safe_pending_details_only():
    menu = Menu({'pending_enrollment': PENDING_RAW})
    menu.console = Console(record=True, force_terminal=False, width=120)

    handle_enrollment(menu, ['inspect', 'ABCD-EFGH'])

    output = menu.console.export_text()
    assert 'endpoint-1' in output
    assert 'customer@example.test' in output
    assert 'aegis' in output
    assert '1.2.3' in output
    assert 'sensor-1' in output
    assert 'linux/amd64' in output
    assert '2026-08-25T16:00:00Z' in output
    assert '2026-08-25T16:10:00Z' in output
    assert 'SHOULD_NOT_LEAK' not in output
    assert 'csr' not in output.lower()
    assert 'cert' not in output.lower()
    assert 'private' not in output.lower()
    assert menu.sdk.aegis.calls == [{'method': 'inspect_enrollment', 'user_code': 'ABCD-EFGH'}]
    assert menu.paused is True


def test_tui_enrollment_approve_yes_inspects_then_approves():
    menu = Menu({'pending_enrollment': PENDING_RAW})
    menu.console = Console(record=True, force_terminal=False, width=120)

    handle_enrollment(menu, ['approve', 'ABCD-EFGH', '--yes'])

    output = menu.console.export_text()
    assert 'endpoint-1' in output
    assert 'Enrollment approved' in output
    assert menu.sdk.aegis.calls == [
        {'method': 'inspect_enrollment', 'user_code': 'ABCD-EFGH'},
        {'method': 'approve_enrollment', 'user_code': 'ABCD-EFGH'},
    ]
    assert menu.paused is True


def test_tui_enrollment_approve_cancel_does_not_approve():
    menu = Menu({'pending_enrollment': PENDING_RAW})
    with patch('praetorian_cli.ui.aegis.commands.enrollment.Confirm.ask', return_value=False):
        handle_enrollment(menu, ['approve', 'ABCD-EFGH'])

    output = '\n'.join(menu.console.lines)
    assert 'Cancelled' in output
    assert menu.sdk.aegis.calls == [{'method': 'inspect_enrollment', 'user_code': 'ABCD-EFGH'}]
    assert menu.paused is True


@pytest.mark.parametrize(
    ('code', 'expected'),
    [
        ('expired_token', 'Invalid or expired enrollment code'),
        ('access_denied', 'cannot be approved for this account'),
        ('temporarily_unavailable', 'temporarily unavailable'),
        ('invalid_request', 'Enrollment request was invalid'),
    ],
)
def test_tui_enrollment_errors_are_actionable(code, expected):
    menu = Menu({'enrollment_errors': {'inspect': Exception(f'[400] Request failed\nError: {{"error":"{code}"}}')}})

    handle_enrollment(menu, ['inspect', 'ABCD-EFGH'])

    output = '\n'.join(menu.console.lines)
    assert expected in output
    assert '[400] Request failed' not in output
    assert menu.paused is True
