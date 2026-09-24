# AI Hunts

The Hunt commands launch, inspect, and control Guard's automated vulnerability-discovery workflows. They support both scriptable output and fullscreen terminal workflows.

```zsh
guard hunt --help
guard hunt launch
guard hunt list
guard hunt open <HUNT_ID>
```

## Hunt surfaces

| Surface | Launch selection | Typical scope | Execution |
|---------|------------------|---------------|-----------|
| External | `--agent hannibal` | Domains, public IP addresses, and CIDRs | Guard-managed infrastructure |
| Internal | `--internal` | Private IPv4 addresses and CIDRs | One explicitly selected Aegis v2 endpoint |
| Cloud | `--agent hannibal-cloud` | Amazon, Azure, or GCP account roots | Guard-managed infrastructure |
| Web Application | `--agent hannibal-webapp` | Active WebApplication records | Guard-managed infrastructure |
| LLM Application | `--agent hannibal-llm` | Active LLM-backed WebApplication records | Guard-managed infrastructure |

Running `guard hunt launch` in an interactive terminal opens the all-surface
launch wizard. It walks through the surface, scope, endpoint, credentials,
objective, aggressiveness, expiration, finish criteria, guardrails, finding
tag, and final confirmation.

Use flags for automation or when stdout is not a terminal:

```zsh
# External Hunt across all active infrastructure
guard hunt launch --yes --prompt "Find exploitable external paths"

# External Hunt against selected targets
guard hunt launch --scope-mode specific \
  --scope example.com --scope 198.51.100.0/24 --yes

# Cloud Hunt
guard hunt launch --agent hannibal-cloud \
  --scope "#asset#aws#123456789012" --yes

# Web Application or LLM Application Hunt
guard hunt launch --agent hannibal-webapp --scope https://app.example.com --yes
guard hunt launch --agent hannibal-llm --scope https://assistant.example.com --yes

# Internal Hunt through one Aegis v2 endpoint
guard hunt launch --internal \
  --endpoint <ENDPOINT_ID> \
  --scope 10.20.30.0/24 \
  --confirm-endpoint --yes
```

Friendly target names are resolved to canonical Guard entity keys. Ambiguous
references fail closed in non-interactive commands and open a selector in an
interactive terminal. `--select-scope` provides a paginated target selector
and therefore requires an interactive terminal.

### Launch controls

| Option | Purpose |
|--------|---------|
| `--scope-mode all\|specific` | Hunt all External infrastructure or require selected targets |
| `--scope <value>` | Add a key, hostname, IP, URL, or friendly target; repeat as needed |
| `--select-scope` | Search and select targets interactively |
| `--expires <hours>` | Expire the Hunt after 1–72 hours |
| `--scope-level normal\|strict` | Control scope enforcement |
| `--aggressiveness cautious\|balanced\|aggressive` | Control attack aggressiveness |
| `--finish-criteria <text>` | Define conditions for completing early |
| `--guardrails <text>` | Add tighten-only safety restrictions |
| `--custom-tag <tag>` | Tag findings created by the Hunt |
| `--credential <id-or-key>` | Attach a run-scoped credential; repeat with at most one credential per type |
| `--yes` | Use flags and defaults without prompts or fullscreen UI |

## Internal Hunts and Aegis

An Internal Hunt requires at least one scope item and exactly one authorized
Aegis v2 endpoint. The CLI shows whether the endpoint is online before
confirmation. Every target-network operation is pinned to that endpoint; if it
is unavailable, the Hunt waits rather than falling back to Guard-managed
compute.

Review and configure endpoints with the [Aegis v2 guide](aegis.md). Endpoint
host-egress policy applies to every Hunt workload and can prevent the agent
from reaching prohibited IP addresses, networks, or TCP ports.

### Active Directory credentials

Create a credential with an endpoint allowlist. Passwords and hashes use hidden input by default; keytab and ccache material is read from a local file.

```zsh
guard add credential active-directory \
  --endpoint <ENDPOINT_ID> \
  --label "Internal AD" \
  --domain corp.example \
  --username svc-hunt

# Password/hash automation without placing the secret in argv
export HUNT_AD_SECRET='...'
guard add credential active-directory \
  --endpoint <ENDPOINT_ID> \
  --label "Internal AD" \
  --domain corp.example \
  --username svc-hunt \
  --auth-type hash \
  --secret-env HUNT_AD_SECRET

# Authorize an existing credential for another endpoint without reading or rotating it
guard update credential active-directory <CREDENTIAL_ID> \
  --endpoint <ENDPOINT_ID>
```

Pass the resulting credential ID or key with
`guard hunt launch --credential ...`. The Internal Hunt wizard can select one
Active Directory credential and one `web-auth` credential; repeat
`--credential` for scripted launches, with at most one credential per type.
Guard remains authoritative for endpoint and resource compatibility.

## Inspecting and controlling Hunts

| Command | Description |
|---------|-------------|
| `guard hunt list [--status ...] [--details]` | List Hunts for the current account |
| `guard hunt status <id>` | Show overview, scope, findings, projected cost, and endpoint execution status |
| `guard hunt status <id> --workflows` | Browse workflow iterations and steps |
| `guard hunt open <id>` | Open the unified fullscreen operator interface |
| `guard hunt findings <id>` | List vulnerabilities, with optional status/severity filters and evidence |
| `guard hunt memory <id>` | Browse memory interactively |
| `guard hunt memory <id> --item <title>` | Read one memory item |
| `guard hunt memory <id> --item <title> --content <text>` | Create or replace one memory item |
| `guard hunt memory <id> --item <title> --delete` | Delete one memory item after confirmation |
| `guard hunt log <id> [--follow]` | Show finalized iteration summaries |
| `guard hunt chat <id>` | Open live chat in a terminal or print a static transcript otherwise |
| `guard hunt chat <id> --message <text>` | Queue guidance for the active iteration |
| `guard hunt interactions <id> [--watch]` | Review pending approvals and credential requests |
| `guard hunt pause\|resume\|stop <id>` | Change Hunt lifecycle state |
| `guard hunt delete <id>` | Delete the Hunt and artifacts while preserving findings |

Use `--page all` on list/findings commands when the full paginated result is required. Static commands retain deterministic output for scripts.

## Unified Hunt interface

`guard hunt open <HUNT_ID>` provides seven cached views:

1. **Overview** — status, scope, endpoint, agent activity, remaining time, findings, and projected cost
2. **Vulnerabilities** — Hunt findings and expandable evidence
3. **Workflow** — iterations, steps, progress, failures, and exact conversation links
4. **Log** — finalized iteration summaries
5. **Memory** — list, read, create, edit, and delete Hunt memory
6. **Chat** — root and delegated-agent conversations, transcripts, steering, and full-chat launch
7. **Approvals** — pending endpoint and credential interactions

### Keyboard controls

| Key | Action |
|-----|--------|
| Left / Right or `1`–`7` | Change view |
| Up / Down | Change the selected item or conversation |
| Enter | Activate the selected workflow, memory, or chat item |
| Space | Expand or collapse details |
| `r` | Refresh only the active view |
| `m` / `n` | Edit the selected memory item / create a memory item |
| `c` | Open the selected conversation in full chat |
| `i` | Review pending interactions |
| `p` / `u` / `x` | Pause / resume / stop the Hunt |
| Escape, Ctrl+C, or `q` | Return or close |

Views load on first use and are then cached. Switching among cached tabs, or
returning from full chat, does not refetch data. Explicit refresh displays a
blocking animated modal while SDK work and complete rendering run outside
Textual's input loop.

## Live chat and human approval

In full chat:

- Up/Down changes conversations immediately.
- PageUp/PageDown moves through transcript history.
- Ctrl+R explicitly refreshes the selected conversation.
- F8 opens pending interactions.
- Escape or Ctrl+C returns to the previous surface.

Messages steer the selected active conversation. Endpoint approvals can be
allowed or denied from the terminal. Credential and MFA fields are masked,
exchanged through the ephemeral credential broker, and are not stored in
durable conversation messages.

## SDK access

The same functionality is available under `sdk.hunts`, `sdk.conversations`,
`sdk.endpoint_executions`, `sdk.credentials`, and `sdk.aegis`. SDK methods
expose structured records while the CLI adds entity resolution, confirmation,
safe credential entry, and Rich/Textual presentation.
