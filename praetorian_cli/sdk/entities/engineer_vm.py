class EngineerVms:
    """ SDK surface for the ad-hoc per-(engineer, tenant) Engineer VM workspaces.

    Wraps the /engineer-vm REST routes. Every route is gated to Praetorian
    analysts and funnels through the backend's single ownership gate, so a
    vm_id the caller does not own returns 403 (surfaced here as an exception).
    """

    def __init__(self, api):
        self.api = api

    def list(self) -> list:
        """ List the caller's own Engineer VMs. """
        resp = self.api.get('engineer-vm')
        return (resp or {}).get('engineer_vms', []) or []

    def get(self, vm_id: str) -> dict:
        """ Fetch one VM row by id. """
        return self.api.get(f'engineer-vm/{vm_id}')

    def launch(self, tier: str = 'light', restore_snapshot_id: str = '') -> dict:
        """ Launch a new VM, optionally restoring a tenant-owned snapshot. """
        body = {'tier': tier}
        if restore_snapshot_id:
            body['restore_snapshot_id'] = restore_snapshot_id
        return self.api.post('engineer-vm', body)

    def archive(self, vm_id: str) -> dict:
        """ Snapshot the data volume and terminate the instance; revive to restore it. """
        return self.api.delete(f'engineer-vm/{vm_id}', {}, {})

    def revive(self, vm_id: str) -> dict:
        """ Relaunch this VM from its own retained snapshot (non-destructive). """
        return self.api.post(f'engineer-vm/{vm_id}/restore', {})

    def pause(self, vm_id: str) -> dict:
        """ Stop the instance, keeping the volume + SG for a later resume. """
        return self.api.post(f'engineer-vm/{vm_id}/pause', {})

    def resume(self, vm_id: str) -> dict:
        """ Start a paused instance back up. """
        return self.api.post(f'engineer-vm/{vm_id}/resume', {})

    def extend(self, vm_id: str, hours: int = 0) -> dict:
        """ Push the soft expiry out by `hours` (server clamps to the ceiling). """
        body = {'hours': hours} if hours and hours > 0 else {}
        return self.api.post(f'engineer-vm/{vm_id}/extend', body)

    def ssh_cert(self, vm_id: str, public_key: str) -> dict:
        """ Mint a 15-min vm-bound OpenSSH user certificate for `public_key`.

        Returns {certificate, vm_id, gateway_url}. The public key is the only
        client-supplied input; every cert field is computed server-side.
        """
        return self.api.post(f'engineer-vm/{vm_id}/ssh-cert', {'public_key': public_key})

    def code_server_token(self, vm_id: str) -> dict:
        """ Mint a short-lived HS256 token for the browser code-server tab.

        Returns {token, vm_id, gateway_url}.
        """
        return self.api.post(f'engineer-vm/{vm_id}/code-server-token', {})
