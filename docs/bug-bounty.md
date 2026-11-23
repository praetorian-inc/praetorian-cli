# Bug bounty findings feed

The `bounty` commands give Praetorian engineers one queryable view of the
findings sitting across the bug bounty tenants, ranked so the best HackerOne
submission candidates come first.

```zsh
guard bounty --help
guard bounty programs
guard bounty findings
```

Bug bounty tenants are the Guard accounts provisioned as
`guard+<program>-<suffix>@praetorian.com`. `guard bounty programs` lists the
ones you can access along with their program slug. Both commands are limited
to Praetorian users.

## Ranking

Every risk is tagged with a proof level, derived from the record itself:

| Proof | Meaning |
|-------|---------|
| `verified` | Independently confirmed by the verification agent (`proposedBy: cato-agent`, a `**Verified by Praetorian Guard` evidence block, or a `cato-proposed` tag; `cato-reviewed` alone only means the agent looked at it) |
| `demonstrated` | Working proof attached (`demonstrated` timestamp or proposed/published evidence) but not independently verified |
| `detected` | Scanner or fingerprint signal only |

The default sort is severity, then proof, then CVSS, so a verified critical
lands above a detected critical, which lands above a verified high.

Each finding also carries a `hackerone` block populated from the risk-sourced
`hackerone-*` attributes the `hackerone-submit` capability writes when a draft
is saved to HackerOne (`intent_id`, `status`, `program`). Account-level
`hackerone-report-<id>-status` attributes are not per-risk history and are
ignored.

## Filtering

```zsh
# Verified crit/high findings nobody has pushed to HackerOne yet
guard bounty findings --proof verified --h1 unsubmitted

# Only a few programs; match is a substring of the slug or account email
guard bounty findings -P bookingcom -P lowes -P zebra

# Everything on one tenant, including deleted and remediated
guard bounty findings -P zebra --severity all --state all

# Rank by proof first, newest first, top 20
guard bounty findings --sort proof -n 20
guard bounty findings --sort created -n 20
```

| Option | Values | Default |
|--------|--------|---------|
| `-P, --program` | substring of the tenant slug or account, repeatable | all tenants |
| `-s, --severity` | comma-separated `critical,high,medium,low,info,exposure` or `all` | `critical,high` |
| `--state` | `live` (triage + open), `triage`, `open`, `accepted`, `remediated`, `deleted`, `all` | `live` |
| `--proof` | minimum level: `verified`, `demonstrated`, `detected` | any |
| `--h1` | `any`, `submitted`, `unsubmitted` | `any` |
| `--sort` | `severity`, `proof`, `cvss`, `created`, `updated`, `program` | `severity` |
| `--workers` | tenants queried concurrently | 8 |

## Output

In a terminal the result is a table. When stdout is piped the same columns are
emitted as tab-separated rows with a header, so `cut`, `awk` and `grep` work
without flags. `--keys` prints risk keys only and `--details` prints JSON:

```zsh
guard bounty findings --proof verified --keys
guard bounty findings --details | jq -r '.data[] | select(.hackerone.submitted | not) | .key'
```

Each JSON finding has `account`, `program`, `key`, `dns`, `name`, `title`,
`status`, `state`, `severity`, `proof`, `cvss_score`, `source`, `origins`,
`tags`, `proposed_by`, `proposed_comment`, `created`, `updated`,
`demonstrated` and `hackerone`. Tenants that fail to load are reported under
`errors` in the JSON output and as warnings on stderr otherwise; the rest of
the feed still renders.

## SDK

```python
from praetorian_cli.sdk.chariot import Chariot
from praetorian_cli.sdk.keychain import Keychain

sdk = Chariot(Keychain())
tenants = sdk.bounty.tenants(['costco', 'lowes'])
findings, errors = sdk.bounty.findings(programs=['bookingcom'], proof='verified', submitted=False)
```

Per-tenant queries reuse the signed-in keychain's loaded configuration and
token, so fanning out across tenants never re-reads the keychain file or
re-authenticates.
