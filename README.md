# Praetorian CLI and SDK

[![Python Version](https://img.shields.io/badge/Python-v3.9+-blue)](https://www.python.org/)
[![pip Version](https://img.shields.io/badge/pip-v23.0+-blue)](https://pypi.org/project/praetorian-cli/)
[![License](https://img.shields.io/badge/License-MIT-007EC6.svg)](LICENSE)
[![Contributor Covenant](https://img.shields.io/badge/Contributor%20covenant-2.1-007EC6.svg)](CODE_OF_CONDUCT.md)
[![Open Source Libraries](https://img.shields.io/badge/Open--source-%F0%9F%92%9A-28a745)](https://opensource.org/)
[![Contributions Welcome](https://img.shields.io/badge/Contributions-Welcome-brightgreen.svg?style=flat)](https://github.com/praetorian-inc/praetorian-cli/issues)

:link: [Guard Platform](https://guard.praetorian.com)
:book: [Documentation](https://docs.praetorian.com)
:bookmark: [PyPI](https://pypi.org/project/praetorian-cli/)

# Table of Contents

- [Description](#description)
- [Getting Started](#getting-started)
    - [Prerequisites](#prerequisites)
    - [Installation](#installation)
    - [Signing up](#signing-up)
    - [Authentication](#authentication)
- [Using the CLI](#using-the-cli)
    - [Update checks](#update-checks)
- [Operators](#operators)
    - [Interactive Console](#interactive-console)
    - [Install local security tools (optional)](#install-local-security-tools-optional)
    - [Marcus Aurelius AI](#marcus-aurelius-ai)
    - [Security Tools](#security-tools)
    - [Red Team](#red-team)
- [Developers](#developers)
    - [SDK](#sdk)
    - [Developing external scripts](#developing-external-scripts)
    - [Running the test suite](#running-the-test-suite)
    - [Contributing](#contributing)
    - [Support](#support)
    - [License](#license)
- [Backwards Compatibility](#backwards-compatibility)

# Description

Praetorian CLI and SDK are open-source tools for interacting with our products and services. Currently, they support
access to [Guard](https://www.praetorian.com/proactive-cybersecurity-technology/), our
offensive security platform.
<br> The SDK exposes the full set of APIs that the Guard UI uses.
<br> The CLI is a fully-featured companion to the Guard UI.

# Getting Started

## Prerequisites

- Python v3.9 or above
- pip v23.0 or above

## Installation

Install the Python package:

```zsh
pip install praetorian-cli
```

### Install from source (for console branch features)

```zsh
git clone https://github.com/praetorian-inc/praetorian-cli.git
cd praetorian-cli
pip install -e .
```

### Configure authentication

```zsh
guard configure
```

Or set environment variables:
```zsh
export PRAETORIAN_CLI_API_KEY_ID=your-api-key-id
export PRAETORIAN_CLI_API_KEY_SECRET=your-api-key-secret
```

## Signing up

Register for an account for [Guard](https://guard.praetorian.com) using the instructions
in [our documentation](https://docs.praetorian.com/hc/en-us/articles/38048335323547-Account-Creation-and-Attack-Surface-Setup).

## Authentication

Once you can properly access Guard through the UI, you can obtain API credentials by clicking the
Praetorian icon in the top right corner -> User Profile -> API Keys. Be sure to carefully copy the
API credentials you created as you will need to provide them to the CLI for interacting with Guard.

**Note**: SSO Organizations should provision access through API Keys as well.

### Using API Keys

This is the authentication method for CLI. You can authenticate using either a keychain file or environment variables.

#### Using the keychain file

This method stores your API key in a keychain file.

1. Run `guard configure` and follow the prompts to set up authentication.
Use the default values for `profile name`, `URL of backend API`, and `client ID`.
2. It creates `~/.praetorian/keychain.ini`, which should read like this:

```text
[United States]
name = guard
client_id = 795dnnr45so7m17cppta0b295o
api = https://d0qcl2e18h.execute-api.us-east-2.amazonaws.com/chariot
api_key_id = your-api-key-id-here
api_key_secret = your-api-key-here
```

#### Using environment variables

This method uses in-memory environment variables to pass your API key to
the CLI. There is no need for a keychain file on disk. This enables you to choose
a credential storage method suitable for your use cases. To use this method, set the
following environment variables:

```zsh
export PRAETORIAN_CLI_API_KEY_ID=your-api-key-id-here
export PRAETORIAN_CLI_API_KEY_SECRET=your-api-key-here
```

The backend API URL and the Cognito emulator endpoint (`aws_endpoint_url`)
must be HTTPS; the CLI refuses to send credentials over plaintext HTTP. For local development against a loopback endpoint (`localhost`,
`127.0.0.1`, `::1`), set `PRAETORIAN_CLI_ALLOW_HTTP_LOOPBACK=1`.

For more advanced configuration options or managing access in SSO organizations see
[the documentation on configuration](https://github.com/praetorian-inc/praetorian-cli/blob/main/docs/configure.md).

# Using the CLI

The CLI is a command and option utility for accessing the full suite of Guard's API. You can see the documentation for commands
using the `help` option:

```zsh
guard --help
```

As an example, run the following command to retrieve the list of all assets in your account:

```zsh
guard --account guard+example@praetorian.com list assets
```

You can obtain the `account` argument by viewing the email of the first user on the Users page in your Guard account, as shown below:

<img width="482" alt="image" src="https://github.com/user-attachments/assets/7c1024c9-7b74-46b1-87c5-af44671b1ec8" />

To get detailed information about a specific asset, run:

```zsh
guard --account guard+example@praetorian.com get asset <ASSET_KEY>
```

## Update checks

After a command finishes, the CLI may check PyPI for a newer release of
`praetorian-cli` and print a three-line upgrade advisory to stderr. The check is
deliberately quiet and infrequent:

- **At most once every 24 hours.** Every attempt is recorded at
  `${XDG_CACHE_HOME:-~/.cache}/praetorian-cli/update-check.json` *before* the
  request is made, so a refresh that fails — offline, DNS, timeout, a malformed
  response — is rate-limited exactly like one that succeeds, and keeps
  advertising the last version it did learn. Between refreshes the check reads
  that file and makes no network request at all — as long as the record is a
  plain file that belongs to you and is no larger than 64 KiB. Anything else at
  that path is ignored as though it were absent, so the next invocation refreshes
  and replaces it rather than trusting what it found. Commands that start at the
  same instant are *not* excluded from one another: each reads the same stale
  record before any of them writes, so eight simultaneous invocations may each
  refresh once. That is an accepted tradeoff rather than an oversight — all
  eight then write the record, so the following 24 hours are quiet; the gates
  below already skip non-interactive and CI sessions, which leaves simultaneous
  *interactive* invocations rare; and a duplicate refresh costs one CDN-backed
  GET. An exclusion held by path was measured to be worse than none: a claim
  that cannot identify its own holder unlinks a live peer's claim and so defeats
  the very limit it was added to guarantee. Each write is an atomic
  same-directory rename, so a reader always sees one writer's whole record,
  never a torn one. A relative `XDG_CACHE_HOME` is ignored in favour of
  `~/.cache`, as the base-directory spec requires —
  honouring it would put a separate cache in every working directory and so
  defeat the limit outright. If the cache directory cannot be written at all (a
  read-only home, one owned by another user, or one reached through a symlink),
  the check does not run: a probe whose rate we cannot limit is one we do not
  send.
- **Only when a human is watching.** It is skipped unless **both** stdout and
  stderr are a terminal, and skipped when `CI` or `GITHUB_ACTIONS` is set or
  `TERM=dumb`. Piping either stream — `guard list assets | jq` — turns it off.
  A script you launch by hand from your own terminal inherits your terminal, so
  treat the opt-out below, not this gate, as the way to guarantee silence.
- **Never in place of your command's work.** A command that raises skips the
  check, and a group that is only delegating to a subcommand leaves the check to
  the subcommand that does the work. A command that reports an error but still
  exits `0` is the one case where an advisory can follow a visible error.
- **Not on the path you run day to day.** The daily refresh passes a 2-second
  timeout to `requests`, which bounds how long the server may go without
  sending data — not total wall-clock, so DNS, TLS, redirects and a slow trickle
  are outside it. Ordinary failures are swallowed and cannot change your exit
  code; `Ctrl-C` and process-control exceptions raised during the check still
  propagate, by design, so that interrupting the CLI always works.

### Disabling it

```zsh
export PRAETORIAN_CLI_DISABLE_UPDATE_CHECK=1
```

`1`, `true`, `yes` or `on` (any case). Nothing is read or written — no request,
no cache file.

### Privacy

A refresh is an unauthenticated `GET` to `https://pypi.org/pypi/praetorian-cli/json`.
It sends no account, profile, command, or argument — only what any HTTPS request
inherently reveals to the server: your IP address and the fact that some
`praetorian-cli` install asked for the package index at that moment. Because
every attempt is recorded before it is made and concurrent attempts are
excluded, that happens at most once per day per user account on the machine —
several users each get their own cache — so your per-command usage cadence is
not exposed. If contacting
pypi.org at all is unacceptable in your environment, set the variable above.

# Operators

## Interactive Console

The Guard CLI includes a Metasploit-style interactive console for operator-focused engagement workflows.

```zsh
guard console
guard console --account client@example.com
```

The console provides:

- **Engagement management** — switch between accounts, view stats (seeds/assets/risks), create customers, manage vaults
- **Metasploit-style tool selection** — `use <tool>`, `show targets`, `set target`, `execute`
- **All 141 backend capabilities** — any capability can be selected via `use <name>` or `use <#>`
- **Marcus Aurelius AI** — inline queries (`ask`) and multi-turn conversation (`marcus`)
- **Fulltext search** — `find` for Neo4j graph search across all entity types
- **Evidence hydration** — `evidence <risk>` fetches all scattered evidence in one view
- **Report generation** — `report generate` / `report validate`
- **Local tool execution** — run installed Praetorian binaries locally, upload results to Guard
- **Live job tracking** — `status`, `jobs`, real-time tool output from Marcus

### Example session

```
guard > accounts                           # list engagements
guard > use 5                              # switch to engagement #5
guard > assets                             # list assets (scoped to engagement)
guard > risks                              # list risks
guard > show 1                             # drill into risk #1

guard > use brutus                         # select credential tester
guard (brutus) > show targets              # show valid port targets
guard (brutus) > set target 3              # pick target #3
guard (brutus) > run                       # execute (local if installed, remote otherwise)
guard (brutus) > status                    # check job results
guard (brutus) > exit                      # back to main prompt

guard > ask "summarize critical risks"     # one-shot Marcus query
guard > marcus                             # enter multi-turn conversation
marcus > @aurelius scan cloud infra        # delegate to specialist agent
marcus > back

guard > marcus read "vault/sow.pdf"        # have Marcus analyze a file
guard > marcus do "add example.com as seed" # direct instruction
guard > download proofs                     # download all proof files locally
guard > home                                # return to your own account
```

## Install local security tools (optional)

Requires the [GitHub CLI](https://cli.github.com/) (`gh`) to be installed and authenticated:

```zsh
guard run install brutus       # install a specific tool
guard run install all          # install all Praetorian tools
guard run installed            # check what's installed
```

Binaries are downloaded from `praetorian-inc` GitHub releases to `~/.praetorian/bin/`.

## Marcus Aurelius AI

Marcus is Guard's AI operator, accessible from both the CLI and the interactive console.

```zsh
# One-shot queries
guard ask "how many critical risks are there?"
guard ask "show me all assets with port 22 open" --mode query

# File analysis and ingestion
guard marcus read "vault/engagement/sow.pdf"
guard marcus ingest "vault/nessus-export.csv" --findings
guard marcus do "generate an executive summary"
```

In the console, Marcus shows live tool execution:
```
guard > ask "analyze the top risks"
Thinking...
  → query — 14 risks done
  → query — 5 assets done
Found 14 risks across 5 assets...
```

## Security Tools

All 141 Guard capabilities are available through the CLI. Named tools include:

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

### Local execution

Tools can run locally if the binary is installed, with results uploaded to Guard:

```zsh
guard run install brutus           # download from praetorian-inc GitHub
guard run install all              # install everything
guard run tool brutus 10.0.1.5     # runs locally (default if installed)
guard run tool brutus 10.0.1.5 --remote  # force remote execution
guard run installed                # show what's installed locally
```

### Additional CLI Commands

Beyond the standard CRUD commands, the CLI includes:

```zsh
# Fulltext search (Neo4j graph queries)
guard find "example.com"
guard find "CVE-2024" --type risk

# Evidence hydration
guard get risk "#risk#example.com#CVE-2024-1234" --evidence basic
guard get risk "#risk#example.com#CVE-2024-1234" --evidence full

# Reports
guard report generate --title "Q1 Pentest" --client "Acme Corp" --risks "status:OH"
guard report validate --risks "status:OH"

# One-shot Marcus AI query
guard ask "what assets have port 22 open?"

# Marcus subcommands
guard marcus read "vault/sow.pdf"
guard marcus ingest "vault/scope.md" --scope --findings
guard marcus do "add example.com as a seed and start discovery"

# Security tools (local or remote)
guard run tool brutus 10.0.1.5
guard run tool nuclei example.com --remote
guard run install brutus
guard run installed

# Engagement management
guard engagement list
guard engagement create-customer --email ops@acme.com --name "ACME Corp"
guard engagement create-vault --client acme --sow SOW-1234 --sku WAPT --github-user jdoe
```

## Red Team

The `red-team` family drives Praetorian's phishing and red-team infrastructure: the deployment lifecycle,
phishing campaigns, parked domains and their DNS, Mailgun mail delivery, Evilginx phishing proxies, and
payload generation. Like `engagement` and `configuration`, these commands are limited to Praetorian
engineers. The check now runs at the SDK layer as well as the CLI, so the same restriction applies to
scripts and to the MCP server rather than to interactive use alone. Note what that check is: it
compares the email address in the local keychain against a Praetorian suffix, so it is a client-side
operator guardrail against reaching for the wrong tool — not a trust boundary. Anyone able to edit
their own keychain can pass it. Authorization for these operations has to be enforced server-side.

Every `red_team_*` MCP tool is classified sensitive, so none of them is exposed to an MCP client unless
an allow entry names it exactly (see [SDK](#sdk)).

```zsh
# Deployment lifecycle
guard red-team deployment launch
guard red-team deployment details
guard red-team deployment history
guard red-team deployment last-inputs
guard red-team deployment node-schema --tag v1.2.3
guard red-team deployment tags
guard red-team deployment collaborators --collaborators user1@co.com,user2@co.com
guard red-team deployment plan --file builder.json
guard red-team deployment apply --file builder.json          # prompts; --yes skips
guard red-team deployment delete --force                     # prompts; --yes skips

# Campaigns
guard red-team campaign create --file campaign.json
guard red-team campaign targets --id camp-1 --file targets.json
guard red-team campaign authorize --id camp-1                # prompts: sends live phishing email
guard red-team campaign funnel --id camp-1
guard red-team campaign activity --id camp-1 --limit 100
guard red-team campaign delete --key "#campaign#camp-1"      # prompts; --yes skips

# Domain parking, DNS, and Mailgun
guard red-team domain update --file domain.json
guard red-team domain dns-list --domain evil.com
guard red-team domain dns-create --domain evil.com --type A --name www --content 1.2.3.4
guard red-team domain dns-update --domain evil.com --record-id abc123 --type A --name www --content 1.2.3.4
guard red-team domain dns-delete --domain evil.com --record-id abc123   # prompts; --yes skips
guard red-team domain mailgun-status --domain evil.com
guard red-team domain mailgun-provision --domain evil.com
guard red-team domain mailgun-domain-delete --domain evil.com          # prompts; --yes skips
guard red-team domain mailgun-user --username noreply --domain evil.com
guard red-team domain mailgun-user-delete --username noreply --domain evil.com  # prompts; --yes skips

# Evilginx
guard red-team evilginx phishlets --node node-ref-1
guard red-team evilginx phishlet-params --node node-ref-1 --name o365
guard red-team evilginx configure --node node-ref-1 --domain evil.com --phishlet o365 \
    --params-file phishlet-params.json
guard red-team evilginx lures --node node-ref-1
guard red-team evilginx create-lure --node node-ref-1 --path /login
guard red-team evilginx status --node node-ref-1

# Payloads and phishkit nodes
guard red-team payload-generate --shellcode beacon.bin --variables-file payload-vars.json
guard red-team phishkit-nodes --status all
```

Two conventions run through the family:

- **JSON bodies come from stdin or a file.** Commands that take a JSON document read stdin when
  `--file` is omitted; `-f/--file PATH` reads a file instead, and `--file -` names stdin explicitly.
  `deployment apply` is the one body-reading command that also prompts, so there stdin carries both
  the confirmation answer and the payload: either pass `--file` and answer the prompt interactively,
  pass `--yes` to skip it, or prefix the piped payload with `y` on its own line. A bare piped JSON
  body aborts — the prompt consumes the body's first line, rejects it as invalid input, and hits
  end-of-input. That is a safe default rather than a bypass: no valid JSON document can begin with a
  line that is exactly `y` or `yes`, so a payload can never answer its own prompt.
- **Secrets stay off the command line.** Evilginx phishlet parameters (OAuth client IDs and secrets,
  session tokens) and payload template variables can be passed inline with `--params` / `--variables`,
  but an inline value is visible in process listings and shell history. Use `--params-file` /
  `--variables-file` for anything sensitive; supplying both forms of the same value is an error.

Every destructive command — deployment delete, terraform apply, campaign delete, DNS record delete,
Mailgun domain and user delete — prompts for confirmation, and `campaign authorize` prompts because it
starts delivering live phishing email to real recipients. Pass `--yes` to skip a prompt in automation.

# Developers

Both CLI and SDK is open-source in this repository. The SDK is installed along with the `praetorian-cli`
package. You can extend Guard by creating scripts using the SDK.

## SDK

Integrate the SDK into your own Python application with the following steps:

1. Include the dependency ``praetorian-cli`` in your project.
2. Import the Guard class ``from praetorian_cli.sdk.guard import Guard``.
3. Import the Keychain class ``from praetorian_cli.sdk.keychain import Keychain``.
4. Call any function of the Guard class, which expose the full backend API. See example below:

```python
from praetorian_cli.sdk.guard import Guard
from praetorian_cli.sdk.keychain import Keychain

guard = Guard(Keychain(account='guard+example@praetorian.com'))
guard.add('asset', dict(name='example.com', dns='example.com'))
```

The best place to explore the SDK is the code of the CLI, especially
[the handlers of the CLI](https://github.com/praetorian-inc/praetorian-cli/tree/main/praetorian_cli/handlers)

You can inspect the handler code to see how each CLI command is implemented with the SDK.

## Developing external scripts

The CLI has a scripting engine that allow external scripts to be executed within the CLI's framework, taking
advantage of the SDK, `click`, and authentication.

To add those external scripts to the CLI, set the `PRAETORIAN_SCRIPTS_PATH`
environment to point to directories where you store additional extension scripts.

Those external scripts are available under the `script` commands. To see a list of them:

```zsh
guard --account guard+example@praetorian.com script --help
```

For developing scripts, you can refer to
this [readme file](https://github.com/praetorian-inc/praetorian-cli/blob/main/docs/script-development.md).


## Running the test suite

`guard test` runs the integration suites that ship with the package. **Some of
those suites create, modify and delete real entities in whatever account the
selected profile points at**, so the command is gated.

Suites are selected with `-s`/`--suite`:

| Suite | What it runs | Touches a live account? |
| --- | --- | --- |
| `safe` *(default)* | Local, offline unit tests | No |
| `coherence` | End-to-end entity lifecycle tests | **Yes — creates and deletes assets, risks, settings, configurations** |
| `cli` | CLI-level integration tests | **Yes — mutating** |
| `tui` | Terminal UI tests | No |

A bare `guard test` runs the `safe` suite only. It executes with a temporary
`HOME` and with credential environment variables stripped, so it cannot reach
your real credentials.

The mutating suites additionally require:

1. **An explicit profile and account.** Both must be given and non-empty —
   `guard --profile <profile> --account <account> test --suite coherence`.
   There is no fallback: an unset or blank value is an error, so the suite can
   never quietly run against a default profile.
2. **Interactive confirmation.** The command prints the suite, profile, account,
   and whether the suite is live and mutating, then asks you to confirm.
   Declining — or a non-interactive invocation, which cannot confirm — exits
   non-zero without running any test.

```zsh
# Safe by default — no account is touched.
guard test

# Mutating suite: target must be explicit, and you must confirm.
guard --profile "United States" --account guard+scratch@praetorian.com \
    test --suite coherence
```

Never point a mutating suite at a production account. Use a dedicated scratch
account whose contents you are willing to lose.


## Contributing

We welcome contributions from the community, from scripts, to the core CLI and SDK. To contribute, fork this
repository and following the
[GitHub instructions](https://docs.github.com/en/get-started/exploring-projects-on-github/contributing-to-a-project)
to create pull requests.

By contributing, you agree to our [Code of Conduct](CODE_OF_CONDUCT.md).

## Support

If you have any questions or need support, please open an issue
[here](https://github.com/praetorian-inc/praetorian-cli/issues) or reach out via
[support@praetorian.com](mailto:support@praetorian.com).

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

---

# Backwards Compatibility

**Guard** is a rebrand of **Chariot**.

### CLI
The `guard` command is the new primary CLI entry point. The legacy `praetorian chariot` command continues to work:

```zsh
# New (preferred):
guard list assets
guard --account example@praetorian.com list assets
guard configure

# Legacy (still supported):
praetorian chariot list assets
praetorian configure
```

### SDK
Both `Guard` and `Chariot` classes are available and interchangeable:

```python
# New (preferred):
from praetorian_cli.sdk.guard import Guard
guard = Guard(Keychain())

# Legacy (still supported):
from praetorian_cli.sdk.chariot import Chariot
chariot = Chariot(Keychain())
```

### Configuration
The keychain file and environment variables remain unchanged. Existing configurations will continue to work without modification.
