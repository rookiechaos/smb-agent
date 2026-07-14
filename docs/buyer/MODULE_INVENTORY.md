# Module inventory

Status legend:

- **core** — required for the commercial Mac mini product
- **optional** — useful; can ship or omit depending on deal
- **experimental** — not default posture; may change without major bump
- **partner** — customer/partner-shaped reference; not generic brand identity
- **deprecated** — keep for compatibility; do not extend

## Core (`smbagent/`)

| Area | Paths | Notes |
|---|---|---|
| CLI / config | `cli.py`, `config.py` | Typer entry `smbagent` |
| Pipeline | `orchestrator.py`, `pipeline_loop_runner.py`, `pipeline_state.py`, `pipeline_outcome.py` | State machine + outcomes |
| Loop engineering | `loop_controller.py`, `loop_stall.py`, `loop_checkpoint.py`, `loop_search.py`, `loop_policy.py`, `loop_convergence.py`, `loop_engineering.py`, `annealing.py` | Bounded writer–critic control |
| Agents | `agents/` | Qualify, negotiation, plan, coding, validation, humanize, bridge |
| Workspace | `workspace.py`, `workspace_state.py` | Artifact FS + OCC reducer |
| Governance | `approvals.py`, `agent_boundaries.py`, execution guard paths | HITL external actions |
| Runtime | `runtime/` | Workflow queue / skills runtime |
| Transports | `transports/` | Mail / calendar / CRM adapters |
| Monitor / portal | `workflow_monitor.py`, `portal/` | Owner-facing status |
| Trust / readiness | `commercial_readiness.py`, `trust_regression.py`, launch readiness checks | Local gates |
| Templates | `templates/dental`, `real-estate`, `legal` | Vertical starter packs |
| Prompts | `prompts/` | Stage prompts for the smbagent standardized deliverable shape |

## Optional

| Area | Paths | Notes |
|---|---|---|
| Local SLM | `slm/` | Default-off advisory / future local inference |
| Voice | optional `[voice]` deps | MLX ASR on Apple Silicon |
| HTTP serve | `[serve]` + `server/` | Not default Mac mini path; localhost-first |
| Apple containers | `containers/apple/` | Recommended isolation on Mac mini |
| Japan trust templates | `japan_trust/` | Copy per customer via CLI |
| Demo example | `examples/demo-tokyo-dental/` | Sanitized demo artifacts |

## Partner / reference (withheld from SPA)

| Area | Paths | Notes |
|---|---|---|
| Partner/customer workflow packs | Seller `do-not-upload/` only | Not present in the transfer archive |
| Partner demo assets | `do-not-upload/examples/partner-demo/` | Withheld from buyer export |

Buyer guidance: use `smbagent/templates/` + `examples/demo-tokyo-dental/` for demos. Build new workflow packs after close.

## Experimental

| Area | Paths | Notes |
|---|---|---|
| Game studio | `smbagent/game_studio/` | See `smbagent/experimental/README.md` |

## Deprecated shims

| Path | Replacement | Action |
|---|---|---|
| `smbagent/integrations_runtime.py` | `smbagent.transports` | Do not add new imports; remove in a future major after buyer cutover |
| `smbagent/integrations_runtime/` (if present) | `smbagent.transports` | Same |

## Top-level docs map

| Kind | Location |
|---|---|
| Buyer DD (this pack) | `docs/buyer/` |
| Commercial / deploy / legal | repo root `*.md` |
| Internal strategy / roadmap | `internal_doc/` |
| Runtime data (empty in ship tree) | `workspaces/`, `analytics/` |

## Python distribution units

`pyproject.toml` wheel packages: `smbagent`, `slm`.
