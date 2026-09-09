"""
Engineer VM constants and small view helpers.

Mirrors the backend Engineer VM model — keep the tier values in sync with the
API. The Engineer VM is an ad-hoc per-(engineer, tenant) cloud workspace; these
are the only tiers the launch route accepts.
"""

# Instance-class selector (picks the EC2 instance type).
TIERS = ('light', 'general', 'heavy')

# Lifecycle status values travel EV#-prefixed on the wire — the prefix is the
# Status-GSI key the reaper scans on, not a display string.
STATUS_PREFIX = 'EV#'


def status_label(status: str) -> str:
    """ Strip the EV# Status-GSI prefix for display: 'EV#running' -> 'running'. """
    if status and status.startswith(STATUS_PREFIX):
        return status[len(STATUS_PREFIX):]
    return status or ''
