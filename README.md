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
- [Getting started](#getting-started)
    - [Prerequisites](#prerequisites)
    - [Installation](#installation)
    - [Signing up](#signing-up-and-configuration)
- [Interactive Console](#interactive-console)
- [Using the CLI](#using-the-cli)
- [Marcus Aurelius AI](#marcus-aurelius-ai)
- [Security Tools](#security-tools)
- [Using scripts](#using-scripts)
- [Developers](#developers)
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
git checkout console
pip install -e .
```

### Dependencies

The console requires `rich` and `prompt_toolkit`, which are installed automatically:

```
click >= 8.1.7
rich >= 13.0.0
prompt_toolkit >= 3.0.0
textual >= 0.47.0
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

### Install local security tools (optional)

Requires the [GitHub CLI](https://cli.github.com/) (`gh`) to be installed and authenticated:

```zsh
guard run install brutus       # install a specific tool
guard run install all          # install all Praetorian tools
guard run installed            # check what's installed
```

Binaries are downloaded from `praetorian-inc` GitHub releases to `~/.praetorian/bin/`.

## Authentication

Use your Guard API keys. Obtain them from the Guard UI: Praetorian icon → User Profile → API Keys.

# Interactive Console

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

### Additional CLI Commands

Beyond the standard CRUD commands, the CLI includes:

```zsh
# Fulltext search (Neo4j graph queries)
guard find "example.com"
guard find "CVE-2024" --type risk

# Evidence hydration
guard get risk "#risk#example.com#CVE-2024-1234" --evidence

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

# Marcus Aurelius AI

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

# Security Tools

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

To get detailed information about a specific asset, run:

```zsh
guard --account guard+example@praetorian.com get asset <ASSET_KEY>
```

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
