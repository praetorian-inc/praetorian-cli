# Terminology and Definitions

The backend API uses a number of shorthands and mnemonics. They are used in several CLI commands and in the global
search bar. This document explains their semantics.

# Asset statuses

For assets, the `status` field has the following shorthands. These shorthands are used in the
`add`, `update` commands of assets, seeds, and pre-seeds. They are also present in the JSON
output of the `get` and `list` commands of those entities:

| Status | Meaning                                                 |
|--------|---------------------------------------------------------|
| A      | An active asset or seed.                                |
| D      | A deleted asset                                         |
| P      | A pending asset                                         |
| F      | A frozen asset. All scans are stopped on frozen assets. |
| FR     | A frozen asset. All scans are stopped on frozen assets. |

# Risk statuses

For risks, the `status` field has the following shorthands. These shorthands are used in the
`add risk` and `update risk` commands. They are also used in the JSON output
of the `get risk` and `list risk --details` commands:

| Risk status | State                    | Priority |
|-------------|--------------------------|----------|
| TI          | Triage                   | Info     |
| TL          | Triage                   | Low      |
| TM          | Triage                   | Medium   |
| TH          | Triage                   | High     |
| TC          | Triage                   | Critical |
| OE          | Open                     | Exposure |
| OI          | Open                     | Info     |
| OL          | Open                     | Low      |
| OM          | Open                     | Medium   |
| OH          | Open                     | High     |
| OC          | Open                     | Critical |
| IE          | Accepted Risk            | Exposure |
| II          | Accepted Risk            | Info     |
| IL          | Accepted Risk            | Low      |
| IM          | Accepted Risk            | Medium   |
| IH          | Accepted Risk            | High     |
| IC          | Accepted Risk            | Critical |
| RE          | Remediated               | Exposure |
| RI          | Remediated               | Info     |
| RL          | Remediated               | Low      |
| RM          | Remediated               | Medium   |
| RH          | Remediated               | High     |
| RC          | Remediated               | Critical |
| DEF         | Deleted (False Positive) | Exposure |
| DIF         | Deleted (False Positive) | Info     |
| DLF         | Deleted (False Positive) | Low      |
| DMF         | Deleted (False Positive) | Medium   |
| DHF         | Deleted (False Positive) | High     |
| DCF         | Deleted (False Positive) | Critical |
| DES         | Deleted (Out of Scope)   | Exposure |
| DIS         | Deleted (Out of Scope)   | Info     |
| DLS         | Deleted (Out of Scope)   | Low      |
| DMS         | Deleted (Out of Scope)   | Medium   |
| DHS         | Deleted (Out of Scope)   | High     |
| DCS         | Deleted (Out of Scope)   | Critical |
| DED         | Deleted (Duplicate)      | Exposure |
| DID         | Deleted (Duplicate)      | Info     |
| DLD         | Deleted (Duplicate)      | Low      |
| DMD         | Deleted (Duplicate)      | Medium   |
| DHD         | Deleted (Duplicate)      | High     |
| DCD         | Deleted (Duplicate)      | Critical |
| DEO         | Deleted (Other)          | Exposure |
| DIO         | Deleted (Other)          | Info     |
| DLO         | Deleted (Other)          | Low      |
| DMO         | Deleted (Other)          | Medium   |
| DHO         | Deleted (Other)          | High     |
| DCO         | Deleted (Other)          | Critical |

# Job statuses

For jobs, the `status` field has the following shorthands. They are used in the JSON
output of the `get job` and `list jobs --details` commands:

| Job status | Meaning                         |
|------------|---------------------------------|
| JQ         | The job is queued for execution |
| JR         | The job is running              |
| JF         | The job failed                  |
| JP         | The job passed                  |


