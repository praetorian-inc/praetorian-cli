"""
Engineer VM constants and small view helpers.

Mirrors backend/pkg/tabularium/model/engineer_vm.go — keep the tier/status
values in sync with that file. The Engineer VM is an ad-hoc per-(engineer,
tenant) cloud workspace; these are the only values the launch routes accept.
"""

# Instance-class selector (picks the EC2 instance type).
TIERS = ('light', 'general', 'heavy')

# Lifecycle status values travel EV#-prefixed on the wire — the prefix is the
# Status-GSI key the reaper scans on, not a display string.
STATUS_PREFIX = 'EV#'
STATUS_PROVISIONING = 'EV#provisioning'
STATUS_RUNNING = 'EV#running'
STATUS_STOPPED = 'EV#stopped'
STATUS_SNAPSHOTTED = 'EV#snapshotted'
STATUS_PURGED = 'EV#purged'


def status_label(status: str) -> str:
    """ Strip the EV# Status-GSI prefix for display: 'EV#running' -> 'running'. """
    if status and status.startswith(STATUS_PREFIX):
        return status[len(STATUS_PREFIX):]
    return status or ''


def is_running(vm: dict) -> bool:
    """ True when the VM row is in the running state. """
    return (vm or {}).get('status') == STATUS_RUNNING


def is_stopped(vm: dict) -> bool:
    """ True when the VM is stopped. """
    return (vm or {}).get('status') == STATUS_STOPPED


def is_snapshotted(vm: dict) -> bool:
    """ True when the VM is snapshotted. """
    return (vm or {}).get('status') == STATUS_SNAPSHOTTED
