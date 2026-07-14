# Architecture overview

## Product shape

```text
                    ┌─────────────────────────────┐
                    │  Company Mac mini / MacBook │
                    │  (single-tenant boundary)   │
                    └──────────────┬──────────────┘
                                   │
         ┌─────────────────────────┼─────────────────────────┐
         │                         │                         │
         ▼                         ▼                         ▼
   Owner monitor            Employee entry            Maintainer CLI
   (read-only)              (narrow skills)           (SSH / smbagent)
         │                         │                         │
         └─────────────────────────┼─────────────────────────┘
                                   │
                                   ▼
                    ┌─────────────────────────────┐
                    │   workspaces/<customer_id>/ │
                    │   artifacts + approvals     │
                    │   runs/ + monitor.html      │
                    └─────────────────────────────┘
```

Commercial posture: **one company, one machine, one governed backend**.
Not a shared multi-tenant SaaS control plane.

## Two runtime shapes

1. **Standardized customer build pipeline**  
   Produces landing page + agent-skills + integration stubs.
2. **Governed workflow backend**  
   Company context, approvals, monitoring, buyer-built workflow packs.

## Build pipeline

```text
Qualify → Negotiate → Plan → (Code ↔ Validate)*N → optional Humanize
```

| Stage | Role | Typical public outputs |
|---|---|---|
| Qualify | Go / no-go | `qualification.json` |
| Negotiate | Requirements | `requirements.json`, `company_context.json` |
| Plan | Architecture under tier caps | `plan.md`, `tasks.json` |
| Coding | Implement deliverable | `code/` |
| Validation | Independent audit | `runs/round-N/verdict.json` |
| Humanize | JP naturalness loop | `humanize-round-N/` |

Agents share **public artifacts only**. Coding and validation are isolated
surfaces (Claude coding vs Codex validation snapshot). Hidden chain-of-thought,
vendor session memory, and raw coding logs are forbidden validation inputs.

## Control plane (loop engineering)

Bounded loops are first-class:

| Concern | Mechanism |
|---|---|
| State | Artifact-derived `derive_state()` + `enforce_pipeline_transition()` |
| Replay audit | `transitions.jsonl` + `smbagent replay --verify` |
| Stall | Issue fingerprint / summary repeat / convergence plateau |
| Search | continue / replay / branch / stop / escalate |
| Checkpoints | `runs/round-N/code_checkpoint/` |
| Graduated terminals | `stopped_by_loop_policy`, `escalated_by_loop_policy`, `humanize_exhausted` |
| Cost | Monthly API budget guard |
| Learning | `failure_memory.jsonl`, `loop_memory.jsonl`, maintainer `tune` |

## Trust model (two lanes)

```text
Unattended lane          HITL lane
─────────────────        ────────────────────────────
plan / draft / analyze   email / calendar / CRM / deploy
workspace-local writes   ProposedExternalAction
                         → schema validate
                         → semantic safety scan
                         → governance.enforce_action
                         → human approval log
```

Defaults: `SMBAGENT_EXTERNAL_EXECUTION_POLICY=hitl`,
`SMBAGENT_ALLOW_UNATTENDED_EXTERNAL_WRITES=false`.

## State write contract

Public workspace sections publish through a revisioned OCC + reducer layer
(`smbagent/workspace_state.py`). Append-only logs (transitions, failure memory,
approvals) stay append-only by design. See
[`../../internal_doc/STATE_WRITE_CONTRACT.md`](../../internal_doc/STATE_WRITE_CONTRACT.md).

## Package layout (high level)

| Path | Role |
|---|---|
| `smbagent/` | Core library + CLI + portal helpers |
| `slm/` | Optional local SLM (default off) |
| `portal/` | JA role-separated HTML entry surfaces |
| `japan_trust/` | Trust / notice templates |
| `containers/apple/` | Apple container image contracts |
| `tests/` | Trust / governance / loop regression |
| `docs/buyer/` | This due-diligence pack |

## Observability surfaces

| Audience | Surface |
|---|---|
| Owner / 経営者 | `monitor.html`, portal owner view |
| Employee / 従業員 | Narrow portal / skills entry |
| Maintainer | CLI, operator dashboard, `maintenance_report.json` |
