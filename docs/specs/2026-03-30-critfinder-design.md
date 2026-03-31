# CritFinder: Adversarial Vulnerability Research Pipeline for Guard

**Date**: 2026-03-30
**Author**: AJ Hammond
**Status**: Approved

## Overview

CritFinder is an adversarial three-agent vulnerability research pipeline integrated into Guard's Marcus AI system. It systematically discovers critical vulnerabilities in engagement attack surfaces through a structured hypothesize-challenge-validate kill chain.

```
SCANNER ──hypotheses──> GATEKEEPER ──approved──> EXPLOITER ──> CONFIRMED VULNS
   ^                       |                        |
   └── rejected/rework ────┘                        |
   └── adjacent findings ───────────────────────────┘
```

## Architecture: Backend-First with CLI Enrichment

All four agents (coordinator, scanner, gatekeeper, exploiter) are backend agent definitions in Guard's agent system. The CLI is a thin client that streams progress. Marcus can invoke CritFinder from any surface (CLI, web UI, API).

### Agent Definitions

Four new files in `guard/backend/pkg/lib/agent/agents/`:

**`research-coordinator.md`** (name: `research-coordinator`)
- Parents: `agent`
- Tools: `query`, `schema`, `activate_skill`, `spawn_agent`, `rag`, `capabilities`
- Skills: `critfinder-methodology`
- Allowed agents: `research-scanner`, `research-gatekeeper`, `research-exploiter`
- Not a capability (invoked conversationally)
- Responsibilities:
  1. Parse request: mode (offensive default / novel / knowledge), scope, depth
  2. If no target: query graph, score attack surface, auto-select targets
  3. Spawn scanner → receive hypotheses
  4. For each hypothesis: spawn gatekeeper → route verdict
  5. For approved: spawn exploiter → collect results
  6. Handle NEEDS REWORK routing (max 2 cycles per hypothesis)
  7. If depth > 1: re-cycle with narrowed scope + denied salvageable elements
  8. Persist: Risk entities, research artifact, engagement metadata
  9. Emit structured progress messages for streaming

**`research-scanner.md`** (name: `research-scanner`)
- Parents: `root`
- Tools: `query`, `schema`, `activate_skill`, `rag`, `capabilities`
- Skills: `vulnerability-hypothesis-format`
- No `job`, no `spawn_agent` — theorizes, never acts
- Output: Structured hypotheses (HYP-001..N) via `finalize`

**`research-gatekeeper.md`** (name: `research-gatekeeper`)
- Parents: `root`
- Tools: `query`, `rag`, `activate_skill`
- Skills: `hypothesis-review-criteria`
- No `job`, no `spawn_agent` — read-only, adversarial
- Output: APPROVED/REJECTED/NEEDS REWORK verdicts via `finalize`

**`research-exploiter.md`** (name: `research-exploiter`)
- Parents: `agent` (full tool access)
- Tools: `query`, `schema`, `job`, `spawn_agent`, `activate_skill`, `file_read`, `rag`
- Skills: `exploitation-and-evidence`
- Allowed agents: `asset-analyzer`, `brutus-agent`, `julius-agent`, `augustus-agent`, `aurelian-agent`, `titus-agent`
- Output: CONFIRMED vulnerabilities or DENIED hypotheses via `finalize`

### Marcus Integration

Add `research-coordinator` to `aurelius.md` (`name: agent`) `allowed_agents` list. Marcus auto-detects research intent ("find vulns", "hunt", "critfinder", "research") and spawns the coordinator.

### Skill Definitions

Four new files in `guard/backend/pkg/lib/agent/skills/`:

**`critfinder-methodology.md`** — Attack surface scoring heuristic, mode selection, depth/cycling rules, progress message format.

**`vulnerability-hypothesis-format.md`** — HYP-XXX format (CWE, primitive, impact, attack narrative, assumptions, confidence, validation steps, prior art). Vulnerability primitives catalog. Scoring criteria. Novelty weighting.

**`hypothesis-review-criteria.md`** — Verdict definitions, challenge checklist, P0/P1/P2 priority, calibration rule (>80% rejection = recalibrate).

**`exploitation-and-evidence.md`** — Validation methodology, CONFIRMED/DENIED output formats, CVSS 3.1, escalation criteria, evidence collection for Risk entity creation.

### Modes

- **Default (offensive)**: Find critical vulnerabilities. CVEs, misconfigs, chains — whatever gets the client popped. Pragmatic.
- **Novel (`--novel`)**: Hunt for 0days and new variants. Novelty bias cranked up, deprioritize known CVEs unless genuinely new chain/variant.
- **Knowledge (`--mode knowledge`)**: Research a specific CVE or technique using Guard data + web sources. Secondary mode.

### Data Flow

1. Coordinator receives request (scope, mode, depth)
2. If no target: query graph → score attack surface → select top targets
3. Spawn scanner with target data, engagement context, mode
4. Scanner returns HYP-001..HYP-N as structured JSON
5. For each hypothesis:
   a. Spawn gatekeeper with hypothesis + target context
   b. APPROVED → queue for exploiter
   c. NEEDS REWORK → respawn scanner with rework notes (max 2x)
   d. REJECTED → archive with reason
6. For each approved hypothesis:
   a. Spawn exploiter with hypothesis + gatekeeper notes
   b. CONFIRMED → create Risk entity + evidence
   c. DENIED → archive, feed salvageable elements to next cycle
7. Persist research artifact (full narrative)
8. Update engagement metadata

### Persistence

| Entity | Content |
|--------|---------|
| Risk (per confirmed finding) | Title, CVSS, CWE, description, PoC, impact, remediation. Linked to affected Asset/Port. Source: `critfinder`. |
| File (research artifact) | `proofs/critfinder/{run-id}/REPORT.md` — full narrative. |
| Attribute (engagement metadata) | `critfinder_runs`: `{date, scope, mode, depth, hypotheses_generated, approved, confirmed, denied, duration}` |

### Progress Streaming

Coordinator emits structured progress lines:

```
[critfinder] Scoring attack surface... 47 assets, 203 ports
[critfinder] Selected targets: k8s.client.com (score: 0.91), api.client.com (score: 0.87)
[scanner]    Analyzing k8s.client.com...
[scanner]    Generated 5 hypotheses (3 high-confidence)
[gatekeeper] Reviewing HYP-001: Kubelet API unauthenticated access... APPROVED (P0)
[gatekeeper] Reviewing HYP-002: etcd exposed without TLS... APPROVED (P1)
[gatekeeper] Reviewing HYP-003: SSRF via webhook admission... NEEDS REWORK
[scanner]    Reworking HYP-003 with gatekeeper feedback...
[gatekeeper] Reviewing HYP-003v2: SSRF via mutating webhook → node metadata... APPROVED (P1)
[gatekeeper] Reviewing HYP-004: CVE-2024-XXXX privilege escalation chain... APPROVED (P0)
[gatekeeper] Reviewing HYP-005: Theoretical race in scheduler... REJECTED (unrealistic preconditions)
[exploiter]  Validating HYP-001: Running nuclei k8s-kubelet-unauth...
[exploiter]  HYP-001 CONFIRMED — Kubelet API returns pod list without auth (CVSS 9.8)
[exploiter]  Validating HYP-004: Spawning asset-analyzer for CVE chain validation...
[exploiter]  HYP-004 CONFIRMED — CVE-2024-XXXX escalation viable from pod → node (CVSS 9.1)
[exploiter]  Validating HYP-002: Running nuclei etcd-unauth...
[exploiter]  HYP-002 DENIED — etcd behind mTLS, scanner missed cert config
[exploiter]  Validating HYP-003v2: Testing SSRF...
[exploiter]  HYP-003v2 CONFIRMED — webhook SSRF reaches node metadata endpoint (CVSS 8.6)
[critfinder] Run complete. 3 confirmed, 1 denied, 1 rejected. 3 risks created.
```

## CLI Surface

### Entry Points

1. **Top-level**: `guard critfinder [target] [options]`
2. **Marcus subcommand**: `guard marcus research [target] [options]`
3. **Console**: `critfinder [target]` or `marcus research [target]`

All three call the same backend path.

### CLI Command

```
guard critfinder                           # full engagement, default depth
guard critfinder k8s.client.com            # scoped to target
guard critfinder --depth 3                 # iterative deep hunt
guard critfinder --novel                   # 0day hunting mode
guard critfinder --mode knowledge CVE-2024-1234  # knowledge research
```

### Implementation

- `handlers/critfinder.py` — top-level `guard critfinder` command
- `handlers/marcus.py` — `guard marcus research` subcommand
- `ui/console/commands/marcus.py` — console `critfinder` / `research` commands
- Streaming via conversation polling with structured progress line parsing
- Color coding: scanner=cyan, gatekeeper=yellow/red/orange, exploiter=green/red, escalation=bold red

## Feature Parity with Local Research Skills

The backend agents maintain full feature parity with the local Claude Code research-scanner/gatekeeper/exploiter skills:

- Hypothesis format: HYP-XXX with CWE, primitive, impact, attack narrative, assumptions, confidence, validation steps, prior art
- Gatekeeper verdicts: APPROVED/REJECTED/NEEDS REWORK with critique, missed mitigations, novelty assessment, revised impact, exploitation priority
- Rework loop: max 2 cycles per hypothesis
- One-at-a-time processing: serialize through full pipeline
- Exploiter PoC format: title, CVSS 3.1, root cause, attack vector, PoC, impact demo, reliability, mitigations, detection, disclosure recommendation
- DENIED feedback loop: salvageable elements cycle back on depth > 1
- Calibration rule: gatekeeper recalibrates if rejecting >80%
- Escalation: pre-auth RCE in critical infra → halt and notify
- CVE findings: surface validated CVEs and chains, not just novel — novelty is a preference knob, not a filter
