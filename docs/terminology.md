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
| F            | A frozen asset. All scans are stopped on frozen assets.                                                                                                                                        |
| FL           | A frozen asset, originally scanned only for discovery. All scans are stopped on frozen assets.                                                                                                 |                                                                                       
| FH           | A frozen asset, originally scanned comprehensively. All scans are stopped on frozen assets.                                                                                                    |                                                                                      

# Risk statuses

For risks, the `status` field has the following shorthands. These shorthands are used in the
`add risk` and `update risk` commands. They are also used in the JSON output
of the `get risk` and `list risk --details` commands:

| Risk status | State      | Priority |
|-------------|------------|----------|
| TI          | Triage     | Info     |
| TL          | Triage     | Low      |
| TM          | Triage     | Medium   |
| TH          | Triage     | High     |
| TC          | Triage     | Critical |
| IE          | Ignored    | Exposure |
| II          | Ignored    | Info     |
| IL          | Ignored    | Low      |
| IM          | Ignored    | Medium   |
| IH          | Ignored    | High     |
| IC          | Ignored    | Critical |
| OE          | Open       | Exposure |
| OI          | Open       | Info     |
| OL          | Open       | Low      |
| OM          | Open       | Medium   |
| OH          | Open       | High     |
| OC          | Open       | Critical |
| OX          | Open       | Material |
| RI          | Remediated | Info     |
| RE          | Remediated | Exposure |
| RL          | Remediated | Low      |
| RM          | Remediated | Medium   |
| RH          | Remediated | High     |
| RC          | Remediated | Critical |
| RX          | Remediated | Material |
| DE          | Deleted    | Exposure |
| DI          | Deleted    | Info     |
| DL          | Deleted    | Low      |
| DM          | Deleted    | Medium   |
| DH          | Deleted    | High     |
| DC          | Deleted    | Critical |

# Job statuses

For jobs, the `status` field has the following shorthands. They are used in the JSON
output of the `get job` and `list jobs --details` commands:

| Job status | Meaning                         |
|------------|---------------------------------|
| JQ         | The job is queued for execution |
| JR         | The job is running              |
| JF         | The job failed                  |
| JP         | The job passed                  |


