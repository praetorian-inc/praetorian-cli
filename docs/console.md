# Guard Interactive Console

The interactive console (`guard console`) provides a Metasploit-style operator interface for Guard engagements.

## Starting the Console

```zsh
guard console
guard console --account client@example.com
```

## Commands

### Context & Engagement

| Command | Description |
|---------|-------------|
| `accounts` / `engagements` | List accounts you can access |
| `use <#>` | Switch to an engagement by number (after `accounts`) |
| `switch <email>` | Switch to an engagement by email |
| `home` / `su` | Return to your own account (unimpersonate) |
| `set account <email>` | Set engagement account |
| `set scope <pattern>` | Filter to a domain/asset group |
| `set mode <query\|agent>` | Set Marcus conversation mode |
| `unset scope` | Clear scope filter |
| `show context` | Display current engagement state |
| `configure` / `login` | Configure API keys inline |

### Search & Recon

| Command | Description |
|---------|-------------|
| `search <term>` | Fast prefix search (DynamoDB) |
| `find <term> [--type X]` | Fulltext search (Neo4j graph) |
| `assets` | List assets (respects scope) |
| `risks` | List risks (respects scope) |
| `jobs [filter]` | List jobs |
| `status` | Check status of last job |
| `status <job_key>` | Check status of specific job |
| `info <key>` | Get entity details |
| `show <#>` | Show detail of item # from last listing |
| `download [proofs\|agents\|all]` | Download job outputs to local dir |

### Security Tools (Metasploit-style)

| Command | Description |
|---------|-------------|
| `use <tool>` | Select a capability (by name or number after `capabilities`) |
| `show targets` | Show valid targets for active tool |
| `set target <key\|#>` | Set target (Guard key or number from list) |
| `options` | Show current tool options |
| `execute` / `exploit` / `run` | Run the active tool against target |
| `back` | Deselect current tool |
| `<tool> <target>` | Direct execution (e.g., `nuclei example.com`) |
| `capabilities [name]` | List all backend capabilities (numbered) |
| `install <tool\|all>` | Install binary from GitHub |
| `installed` | List locally installed binaries |

Any of the 141+ backend capabilities can be used via `use <name>`.

### Named Agents

| Agent | Description |
|-------|-------------|
| `asset-analyzer` | Deep-dive reconnaissance & risk mapping |
| `brutus` | Credential attacks (SSH, RDP, FTP, SMB) |
| `julius` | LLM/AI service fingerprinting |
| `augustus` | LLM jailbreak & prompt injection attacks |
| `aurelius` | Cloud infrastructure discovery (AWS/Azure/GCP) |
| `trajan` | CI/CD pipeline security scanning |
| `priscus` | Remediation retesting |
| `seneca` | CVE research & exploit intelligence |
| `titus` | Secret scanning & credential leak detection |

### Marcus Aurelius AI

| Command | Description |
|---------|-------------|
| `ask "<question>"` | One-shot query to Marcus |
| `marcus` | Enter multi-turn conversation mode |
| `marcus read <path>` | Read & analyze a Guard file |
| `marcus ingest <path>` | Read file & auto-create seeds/risks |
| `marcus do "<instruction>"` | Direct instruction (full agent access) |

In marcus conversation mode, prefix commands with `/`:
- `/back` — return to console
- `/new` — start new conversation
- `/query` / `/agent` — switch mode

### Evidence & Reports

| Command | Description |
|---------|-------------|
| `evidence <risk_key>` | Hydrated evidence from all sources |
| `report generate [opts]` | Generate engagement report |
| `report validate [opts]` | Validate report requirements |

### Operations

| Command | Description |
|---------|-------------|
| `scan <asset> [capability]` | Schedule a scan job |
| `tag <risk> <tag...>` | Tag a risk |

## Local Tool Execution

Tools run locally by default if the binary is installed (`~/.praetorian/bin/`), otherwise they schedule a remote job on the Guard backend.

```
guard > install brutus          # download from praetorian-inc GitHub
guard > use brutus
guard (brutus) > 10.0.1.5      # runs locally, uploads results to Guard
```

Use `--remote` to force backend execution, `--local` to force local.

## Target Resolution

Targets can be specified as:
- Guard entity keys: `#asset#example.com#1.2.3.4`
- Friendly names: `example.com`, `10.0.1.5`
- Numbers from the last listing: `1`, `2`, `3`

The console resolves friendly names to Guard keys automatically using fulltext search.
