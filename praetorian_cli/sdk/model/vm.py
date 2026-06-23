"""
Engineer VM constants and small view helpers.

Mirrors backend/pkg/tabularium/model/engineer_vm.go — keep the tier/mode/status
values in sync with that file. The Engineer VM is an ad-hoc per-(engineer,
tenant) cloud workspace; these are the only values the launch routes accept.
"""

# Instance-class selector (picks the EC2 instance type).
TIERS = ('light', 'general', 'heavy')

# Auto-start set baked into the AMI's cloud-init (picks what comes up running).
MODES = ('code-review', 'general-assessment', 'heavy-ops')

# Lifecycle status values travel EV#-prefixed on the wire — the prefix is the
# Status-GSI key the reaper scans on, not a display string.
STATUS_PREFIX = 'EV#'
STATUS_RUNNING = 'EV#running'


def status_label(status: str) -> str:
    """ Strip the EV# Status-GSI prefix for display: 'EV#running' -> 'running'. """
    if status and status.startswith(STATUS_PREFIX):
        return status[len(STATUS_PREFIX):]
    return status or ''


def is_running(vm: dict) -> bool:
    """ True when the VM row is in the running state. """
    return (vm or {}).get('status') == STATUS_RUNNING
