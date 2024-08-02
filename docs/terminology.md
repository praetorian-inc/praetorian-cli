# Terminology and Definitions

The backend API uses a number of shorthands and mnemonics. They are used in several CLI commands and in the global
search bar. This document explains their semantics.

# Asset statuses

For assets, the `status` field has the following shorthands. These shorthands are used in the
`add asset` and `update asset` commands. They are also used in the JSON output
of the `get asset` and `list assets --details` commands:

| Asset status | Meaning                                                                                                                                                                                        |
|--------------|------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| AH           | An active asset. Comprehensive asset and risk discovery scans, including more intensive testing that may generate significant load. Suitable for highly resilient and business critical assets |
| A            | An active asset. Standard asset and risk discovery scans                                                                                                                                       |
| AL           | An active asset. Asset discovery scans only with no risk scanning                                                                                                                              |
| F            | A frozen asset. No scans on this asset                                                                                                                                                         |

# Risk statuses

For risks, the `status` field has the following shorthands. These shorthands are used in the
`add risk` and `update risk` commands. They are also used in the JSON output
of the `get risk` and `list risk --details` commands:

| Risk status | State                   | Priority |
|-------------|-------------------------|----------|
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
| CIF         | Closed (False Positive) | Info     |
| CLF         | Closed (False Positive) | Low      |
| CMF         | Closed (False Positive) | Medium   |
| CHF         | Closed (False Positive) | High     |
| CCF         | Closed (False Positive) | Critical |
| CIR         | Closed (Rejected)       | Info     |
| CLR         | Closed (Rejected)       | Low      |
| CMR         | Closed (Rejected)       | Medium   |
| CHR         | Closed (Rejected)       | High     |
| CCR         | Closed (Rejected)       | Critical |
| CIS         | Closed (Out of Scope)   | Info     |
| CLS         | Closed (Out of Scope)   | Low      |
| CMS         | Closed (Out of Scope)   | Medium   |
| CHS         | Closed (Out of Scope)   | High     |
| CCS         | Closed (Out of Scope)   | Critical |
| M           | Closed (Machine)        | -        |
| MI          | Closed (Machine)        | Info     |
| ML          | Closed (Machine)        | Low      |
| MM          | Closed (Machine)        | Medium   |
| MH          | Closed (Machine)        | High     |
| MC          | Closed (Machine)        | Critical |

# Job statuses

For jobs, the `status` field has the following shorthands. They are used in the JSON
output of the `get job` and `list jobs --details` commands:

| Job status | Meaning                         |
|------------|---------------------------------|
| JQ         | The job is queued for execution |
| JR         | The job is running              |
| JF         | The job failed                  |
| JP         | The job passed                  |

