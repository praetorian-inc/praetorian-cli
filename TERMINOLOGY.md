# Terminology and Definitions

The backend API uses a number of shorthands and mnemonics. In several CLI commands, you need to provide
them. This file documents their semantics.

# Asset statuses

For assets, the `status` field has the following shorthands. These shorthands are used in the
`add asset` and `update asset` commands. They are also used in the JSON output
of the `get asset` and `list assets --details` commands:


| Asset status | Meaning                                                  |
| ------------ | -------------------------------------------------------- |
| A            | Active assets with standard scanning                     |
| AH           | Active assets with comprehensive scanning                |
| AL           | Active assets that are only scanned for asset discovery  |
| F            | Frozen assets. They are not scanned                      |



# Risk statuses

For risks, the `status` field has the following shorthands. These shorthands are used in the
`add risk` and `update risk` commands. They are also used in the JSON output
of the `get risk` and `list risk --details` commands:


| Risk status | Stage                   | Priority |
| ----------- | ----------------------- | -------- |
| T           | Triage                  | -        |
| TI          | Triage                  | Info     |
| TL          | Triage                  | Low      |
| TM          | Triage                  | Medium   |
| TH          | Triage                  | High     |
| TC          | Triage                  | Critical |
| O           | Open                    | -        |
| OI          | Open                    | Info     |
| OL          | Open                    | Low      |
| OM          | Open                    | Medium   |
| OH          | Open                    | High     |
| OC          | Open                    | Critical |
| C           | Closed                  | -        |
| CI          | Closed                  | Info     |
| CL          | Closed                  | Low      |
| CM          | Closed                  | Medium   |
| CH          | Closed                  | High     |
| CC          | Closed                  | Critical |
| CIF         | Closed (false positive) | Info     |
| CLF         | Closed (false positive) | Low      |
| CMF         | Closed (false positive) | Medium   |
| CHF         | Closed (false positive) | High     |
| CCF         | Closed (false positive) | Critical |
| CIR         | Closed (rejected)       | Info     |
| CLR         | Closed (rejected)       | Low      |
| CMR         | Closed (rejected)       | Medium   |
| CHR         | Closed (rejected)       | High     |
| CCR         | Closed (rejected)       | Critical |

# Job statuses

For jobs, the `status` field has the following shorthands. They are used in the JSON 
output of the `get job` and `list jobs --details` commands:

| Job status | Meaning                         |
| ---------- | ------------------------------- |
| JQ         | The job is queued for execution |
| JR         | The job is running              |
| JF         | The job failed                  |
| JP         | The job passed                  |

