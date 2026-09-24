# Engineer VMs

> Engineer VM commands are available only to authenticated Praetorian engineers. Guard enforces authorization server-side.

The `vm` command group manages ad-hoc cloud workspaces for operator tasks:

```zsh
guard vm --help
guard vm list
guard vm launch
```

The legacy entry point exposes the same group as `praetorian chariot vm`.

## Lifecycle

| Command | Description |
|---------|-------------|
| `guard vm list` | List your workspaces with status, tier, private IP, and expiry |
| `guard vm launch [--tier light\|general\|heavy]` | Launch a workspace |
| `guard vm launch --restore-snapshot <id>` | Launch with a tenant-owned data-volume snapshot |
| `guard vm status <vm-id>` | Print full VM details |
| `guard vm pause <vm-id>` | Stop compute while retaining the volume and security group |
| `guard vm resume <vm-id>` | Restart a paused VM |
| `guard vm extend <vm-id> [--hours N]` | Extend the soft expiry; default is seven days, bounded by the 30-day ceiling |
| `guard vm archive <vm-id>` | Snapshot the data volume and terminate compute after confirmation |
| `guard vm revive <vm-id>` | Reprovision an archived VM from its retained snapshot |

Example lifecycle:

```zsh
guard vm launch --tier general
guard vm status <VM_ID>
guard vm extend <VM_ID> --hours 24
guard vm pause <VM_ID>
guard vm resume <VM_ID>
guard vm archive <VM_ID> --yes
guard vm revive <VM_ID>
```

A launched or revived VM may remain in provisioning for several minutes. Use `guard vm status` until its phase is running.

## SSH access

```zsh
guard vm ssh <VM_ID>
guard vm ssh <VM_ID> -- -L 8443:127.0.0.1:8443
guard vm ssh <VM_ID> --user engineer
```

The CLI:

1. creates an ephemeral Ed25519 keypair in a temporary directory;
2. requests a VM-bound SSH certificate valid for approximately 15 minutes;
3. connects through Guard's authenticated WebSocket gateway; and
4. removes the temporary key and certificate when SSH exits.

No AWS credentials are required, and the Guard token is not placed in the SSH process arguments. The gateway connection uses normal TLS certificate verification.

Arguments after the VM ID are forwarded to the local `ssh` client. Both `ssh` and `ssh-keygen` must be installed and available on `PATH`.

## Browser IDE

```zsh
guard vm code-server <VM_ID>
guard vm code-server <VM_ID> --no-browser
```

The command requests a short-lived access token. By default it opens the code-server URL in a browser; `--no-browser` prints the URL instead.

Treat the printed URL as sensitive until its token expires. Do not place it in logs or shared tickets.

## SDK access

Engineer VM lifecycle and access-token methods are available from `sdk.vms`. Authorization failures are returned by Guard as HTTP 403 responses.
