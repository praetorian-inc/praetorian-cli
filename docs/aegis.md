# Aegis endpoints

The Aegis CLI manages legacy agents and Aegis v2 endpoints. Aegis v2 adds
durable endpoint identity, enrollment approval, native capability execution,
endpoint-bound AI Hunts, host egress policy, and explicit execution lifecycle
controls.

```zsh
guard aegis list
guard aegis list --details
guard aegis                         # interactive endpoint console
```

The endpoint inventory includes connected and disconnected Aegis v2 endpoints.
In the interactive console, use `list --all` to include offline endpoints and
`set <number|endpoint-id|hostname>` to select one.

## Enrollment

Aegis v2 enrollment uses the short user code shown by the endpoint. Inspection returns only safe enrollment metadata; certificate and key material are never printed.

```zsh
guard aegis enrollment inspect ABCD-EFGH
guard aegis enrollment approve ABCD-EFGH
guard aegis enrollment approve ABCD-EFGH --yes
```

Approval is account-scoped and requires endpoint-management permission. Expired codes must be regenerated on the endpoint.

## Interactive endpoint console

Run `guard aegis`, select an endpoint with `set`, and then use these commands:

| Command | Description |
|---------|-------------|
| `list [--all]` | List online endpoints, or all endpoints including offline ones |
| `set <reference>` | Select by row number, endpoint ID, legacy client ID, or unique hostname |
| `info [--raw]` | Show selected endpoint details |
| `job capabilities [--details]` | List capabilities compatible with the selected endpoint |
| `job run <capability>` | Configure and queue one endpoint capability |
| `job list` | List recent jobs for the selected endpoint |
| `hunt launch` | Launch an Internal Hunt through the selected Aegis v2 endpoint |
| `hunt list\|status\|findings\|memory\|log\|chat` | Inspect Hunts assigned to the selected endpoint |
| `hunt pause\|resume\|stop` | Control a selected endpoint's Hunt |
| `policy` | Show endpoint host-egress policy |
| `policy default remove\|restore ...` | Change built-in deny protections |
| `policy deny add\|remove ...` | Change custom address/network deny rules |
| `user add\|remove <username>` | Queue Linux user management on Aegis v2 |
| `tunnel status` | Show Aegis v2 tunnel configuration, readiness, and diagnostics |
| `tunnel create\|remove` | Queue Cloudflare tunnel configuration changes |
| `ssh`, `cp`, `proxy` | Access or transfer data through a configured tunnel |
| `enrollment inspect\|approve` | Inspect or approve an Aegis v2 enrollment code |

Use `help` inside the console for examples and available shortcuts. Commands that are not valid for a legacy agent or unsupported endpoint capability fail before dispatch.

## Endpoint capabilities

Aegis v2 capability discovery is endpoint-aware. `job capabilities` shows only
native capabilities compatible with the selected endpoint kind and operating
system. `job run` collects target, configuration, and compatible credentials
before creating the native endpoint task.

Endpoint execution is represented by sessions, tasks, and operations. Use the top-level commands when you need deterministic status or cancellation outside the interactive console:

```zsh
guard agent endpoint status <CONVERSATION_ID>
guard agent endpoint operation <SESSION_ID> <OPERATION_ID>
guard agent endpoint operation <SESSION_ID> <OPERATION_ID> --download ./artifacts

guard agent endpoint stop-conversation <CONVERSATION_ID>
guard agent endpoint cancel-session <CONVERSATION_ID>
guard agent endpoint cancel-task <ENDPOINT_ID> <TASK_ID>
guard agent endpoint cancel-operation <SESSION_ID> <OPERATION_ID>
```

Downloaded operation artifacts are verified before the CLI reports their
paths. Cancellation uses Guard's authoritative conversation/session/task
lifecycle rather than only stopping local output.

## Endpoint-bound Hunts

Internal Hunts pin all target-network work to one Aegis v2 endpoint. There is
no Guard-compute fallback: if the endpoint becomes unavailable, work waits
until endpoint execution can continue.

From the endpoint console:

```text
set <ENDPOINT_ID>
hunt launch --prompt "Assess the approved internal scope"
hunt status <HUNT_ID> --workflows
hunt chat <HUNT_ID>
```

For all Hunt surfaces and non-interactive launch options, see [AI Hunts](hunts.md).

## Linux users and Cloudflare tunnels

Aegis v2 management tasks can add or remove a Linux user and create or remove the endpoint's Cloudflare tunnel:

```text
user add pentester --yes
user remove pentester --remove-home
tunnel status
tunnel create --yes
tunnel remove
```

`tunnel status` is available for Aegis v2 endpoints and reports durable
configuration, runtime/readiness reason, observation time, authorized users,
service/connector/origin health, the latest error, and bounded network
diagnostics when available.

Create and remove queue management tasks; they do not modify the local machine.
Tunnel state is read from canonical endpoint inventory and persisted tunnel
status, so configured/running tunnels remain visible across endpoint
reconnects.

## Host egress network policy

Aegis v2 network policy restricts every active and future workload on an endpoint, including agentic Hunt workloads. Policies are tenant-owned and enforced by the endpoint host.

### Inspect policy

```zsh
guard aegis network-policy show <ENDPOINT_ID>
```

The response includes:

- desired and applied revisions;
- host-validation and application status;
- application errors;
- protected gateway, DNS, and Docker DNS addresses;
- enabled or removed built-in deny rules; and
- numbered custom deny rules.

Inside `guard aegis`, select the endpoint and run `policy` for the same view.

### Built-in deny rules

| Rule ID | Protection |
|---------|------------|
| `deny-unspecified` | Unspecified IPv4 address |
| `deny-loopback` | Host IPv4 and IPv6 loopback destinations |
| `deny-docker-api` | Docker API ports on local endpoint addresses |
| `deny-control-plane` | Resolved Guard endpoint-control and session-gateway addresses |

Remove or restore a built-in rule explicitly:

```zsh
guard aegis network-policy default remove <ENDPOINT_ID> deny-loopback
guard aegis network-policy default restore <ENDPOINT_ID> deny-loopback
```

Removing loopback, Docker API, or control-plane defaults displays an additional
exposure warning. Persistent-session sandbox isolation still applies its own
loopback and Docker API restrictions.

### Custom deny rules

Destinations must be canonical IPv4/IPv6 addresses or CIDRs. Hostnames are
intentionally rejected because their resolved addresses can change. Omit
`--tcp-ports` to deny all traffic to the destination.

```zsh
# Deny all workload traffic to a network
guard aegis network-policy deny add <ENDPOINT_ID> 10.20.30.0/24

# Deny selected TCP ports to one address
guard aegis network-policy deny add <ENDPOINT_ID> 198.51.100.7 \
  --tcp-ports 22,443

# Remove by the number printed by `show`
guard aegis network-policy deny remove <ENDPOINT_ID> 1

# Or remove an exact destination/port rule
guard aegis network-policy deny remove <ENDPOINT_ID> 198.51.100.7 \
  --tcp-ports 22,443
```

Every mutation loads the current policy and sends its expected revision,
preventing silent overwrites when another operator saves first. Changes require
confirmation unless `--yes` is supplied. Guard rejects invalid policies and
rules that conflict with protected gateway or DNS connectivity.

Editing is read-only when the endpoint is revoked, disconnected, or does not
advertise the required policy capability. Application status can briefly remain
pending while the endpoint reconciles the desired revision.

## SDK access

Structured endpoint operations are exposed through:

- `sdk.aegis` — inventory, enrollment, management tasks, tunnels, and network policy;
- `sdk.capabilities` — endpoint-compatible capability discovery;
- `sdk.endpoint_executions` — conversation, session, task, operation, artifact, and cancellation APIs; and
- `sdk.hunts` — endpoint-bound Hunt status and lifecycle.
