# smbagent — Detailed Framework Introduction (English)

This document is the **detailed English introduction to the whole `smbagent` code framework**: what it is, how it is structured, how data flows, and how to operate it.

Shorter product intro: [`../../INTRODUCTION.md`](../../INTRODUCTION.md)  
Japanese detailed guide: [`FRAMEWORK_GUIDE_JA.md`](FRAMEWORK_GUIDE_JA.md)  
Transfer one-pager: [`TRANSFER_ONEPAGER_EN.md`](TRANSFER_ONEPAGER_EN.md)

---

## 1. What this framework is

`smbagent` is a **trustable, single-tenant AI operations backend** for Japanese SMBs.

| It is | It is not |
|---|---|
| One company · one Mac mini/MacBook · one governed backend | Multi-tenant ChatGPT SaaS |
| Supervised automation with human approval at risk edges | Fully autonomous “AI employee” |
| Artifact-first multi-agent build + ops system | Prompt-only toy agent |
| Auditable, recoverable, monitorable | Black-box always-on companion |

**One-line pitch**

> One company, one Mac mini, one governed AI backend.

Commercial transfer scope: the buyer receives this **complete framework**.
Seller-withheld partner/customer workflow packs may live only under
`do-not-upload/` — that does **not** remove the framework.

---

## 2. Repository map (top level)

```text
smbagent/                 # Python package — core framework (the product)
slm/                      # Optional local SLM scaffold (default-off)
portal/                   # Role-separated HTML entry (owner / employee / operator)
japan_trust/              # Japan SMB trust / notice templates
containers/apple/         # Apple container image contracts
examples/demo-tokyo-dental/  # Sanitized end-to-end demo
tests/                    # Regression / trust suites
docs/buyer/               # Acquisition & framework guides (this folder)
internal_doc/             # Roadmap, philosophy, operator depth
workspaces/               # Runtime customer data (empty placeholders in ship tree)
do-not-upload/            # Seller-only (never shipped) — pricing, withheld packs, local junk
```

Install entry: `pyproject.toml` → CLI command `smbagent`.

---

## 3. Two product shapes inside one framework

### A. Standardized customer build pipeline

Turns a Japanese business brief / negotiation into a deliverable package:

1. Branded landing page (`code/landing-page/`)
2. Customer-facing AI skills (`code/agent-skills/`)
3. Integration stubs (`code/integrations/` — mail, calendar, CRM)

### B. Governed workflow backend

Runs ongoing company operations with:

- company context
- approvals / HITL
- owner monitor
- failure / loop memory
- maintainer tuning and readiness checks

Both shapes share the same trust model and workspace boundary.

---

## 4. End-to-end architecture

```text
                 Company Mac mini (single-tenant boundary)
                 ┌──────────────────────────────────────┐
                 │  smbagent CLI / optional localhost   │
                 │  portal / owner monitor             │
                 └──────────────────┬───────────────────┘
                                    │
         ┌──────────────────────────┼──────────────────────────┐
         ▼                          ▼                          ▼
   Owner (read-only)         Employee (narrow)          Maintainer (SSH/CLI)
         │                          │                          │
         └──────────────────────────┼──────────────────────────┘
                                    ▼
                    workspaces/<customer_id>/
                    ├── qualification.json, requirements.json, plan.md, …
                    ├── code/
                    ├── runs/round-N/  (+ checkpoints, verdicts)
                    ├── approvals, monitor, transitions.jsonl
                    └── pipeline_outcome.json (when graduated terminal)
```

**Isolation rule:** agents communicate through **public artifacts only**.  
They must not share hidden chain-of-thought, vendor session memory, or raw coding logs as validation inputs.

---

## 5. Build pipeline (five stages + loops)

```text
Qualify → Negotiate → Plan → (Code ↔ Validate)*N → optional Humanize
```

| Stage | Module area | Public outputs |
|---|---|---|
| Qualify | `agents/qualify.py` | `qualification.json` |
| Negotiate | `agents/negotiation.py` | `requirements.json`, `company_context.json`, transcript |
| Plan | `agents/plan.py` | `plan.md`, `tasks.json` (+ tier-cap enforcement) |
| Coding | `agents/coding.py` | `code/` tree |
| Validation | `agents/validation.py` | `runs/round-N/verdict.json`, feedback |
| Humanize | `humanize_loop.py`, humanize agents | `humanize-round-N/` |

Driver: `orchestrator.py` → `pipeline_loop_runner.py` for Code↔Validate.

Coding and validation are **separate surfaces** (typically Claude coding vs Codex validation snapshot). Validation reads a sanitized snapshot, not private coding memory.

---

## 6. Loop engineering (why this is not an infinite agent)

Bounded iteration is a first-class subsystem:

| Concern | Key modules | Behavior |
|---|---|---|
| Unified writer↔critic driver | `loop_controller.py` | Shared humanize / A↔B loop control |
| Stall detection | `loop_stall.py` | Repeated issues / summaries / plateau |
| Temperature schedule | `annealing.py` | creative → convergence → final |
| Search policy | `loop_search.py` | continue / replay / branch / stop / escalate |
| Checkpoints | `loop_checkpoint.py` | Save/restore `code/` per round |
| Convergence metrics | `loop_convergence.py` | Issue delta, code-tree entropy, rubric plateau |
| SLM advisory (optional) | `loop_policy.py`, `slm/` | Confidence-gated prune/boost — not silent autonomy |
| Graduated terminals | `pipeline_outcome.py` | stop / escalate / humanize_exhausted |
| State machine | `pipeline_state.py` | `derive_state()` + `enforce_pipeline_transition()` |
| Audit replay | `observability/transitions.py` | `smbagent replay --verify` |

Philosophy: **fail closed** — stop or escalate rather than burn tokens forever.

Inspect posture:

```bash
smbagent loop-engineering <customer_id>
smbagent loop-policy <customer_id>
smbagent state <customer_id>
```

---

## 7. Trust model (two lanes)

```text
Unattended lane                    HITL lane
─────────────────────────          ────────────────────────────────
plan / draft / analyze             email / calendar / CRM / deploy
workspace-local writes             ProposedExternalAction
                                   → schema (proposed_actions)
                                   → safety semantic scan
                                   → governance.enforce_action
                                   → human approval log
```

Key modules: `execution_guard.py`, `governance.py`, `approvals.py`, `agent_boundaries.py`, `safety.py`.

Defaults (Mac mini commercial posture):

- `SMBAGENT_EXTERNAL_EXECUTION_POLICY=hitl`
- `SMBAGENT_ALLOW_UNATTENDED_EXTERNAL_WRITES=false`
- Prefer `SMBAGENT_SUBPROCESS_ISOLATION=apple-container`

---

## 8. Workspace & state

Each customer is a directory under `workspaces/<customer_id>/`.

| Mechanism | Module | Role |
|---|---|---|
| Artifact FS API | `workspace.py` | Paths, rounds, verdicts |
| Revisioned public state | `workspace_state.py` | OCC + section reducer |
| Formal pipeline state | `pipeline_state.py` | Derive current state from disk |
| Graduated outcome | `pipeline_outcome.py` | Authoritative terminal overlay |

State is **artifact-derived**: you can inspect a workspace offline and know where the run stopped.

---

## 9. Observability & recovery

| Audience | Surface |
|---|---|
| Owner / 経営者 | `monitor.html`, portal owner view, budget posture |
| Employee / 従業員 | Narrow portal / skills entry |
| Maintainer | CLI, operator dashboard, `maintenance_report.json`, `workflow-check` |

Useful commands:

```bash
smbagent monitor <id>
smbagent maintenance <id>
smbagent workflow-check <id>
smbagent backup <id>
smbagent memory-analytics [--customer <id>]
smbagent tune show --customer <id>
```

Learning logs (no raw private CoT): `failure_memory.jsonl`, `loop_memory.jsonl`, usage JSONL, harness manifests.

---

## 10. Vertical templates & demos

Included in the framework:

- `smbagent/templates/dental`
- `smbagent/templates/real-estate`
- `smbagent/templates/legal`
- `examples/demo-tokyo-dental/` — full Growth-tier fictional clinic example

SPA note: seller-withheld partner/customer workflow packs are not in the transfer
archive. Buyers build new workflow packs on top of the framework after close.

---

## 11. Optional layers (still part of the repo)

| Layer | Path | Default |
|---|---|---|
| Local SLM | `slm/` + `smbagent/slm/` | Off — advisory only when enabled |
| Voice ASR/TTS | `smbagent/voice/` + `[voice]` extra | Local MLX ASR preferred on Apple Silicon |
| HTTP server | `smbagent/server/` + `[serve]` | Not default Mac mini path; localhost-first |
| Game studio | `smbagent/game_studio/` | Experimental |

---

## 12. Typical operator path

```bash
python3.11 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev,voice]"
cp .env.example .env          # fill credentials locally — never commit

smbagent doctor
smbagent launch-readiness
smbagent security-readiness

smbagent new acme-dental
smbagent japan-trust-note acme-dental
smbagent qualify acme-dental --brief "Tokyo dental clinic, AI booking + FAQ"
smbagent run acme-dental
smbagent state acme-dental
smbagent monitor acme-dental
```

Clean buyer archive (excludes `do-not-upload/`):

```bash
./scripts/export_product_tree.sh /tmp/smbagent-transfer
```

---

## 13. Human roles (product, not just UX)

| Role | Responsibility |
|---|---|
| Owner / boss | Read-only visibility: status, budget, whether AI work is bounded |
| Employee | Narrow entry points only — not full admin power |
| Maintainer / operator | Install, SSH, approvals, tuning, backup, incident response |

This separation is part of the trust story for Japanese SMB buyers.

---

## 14. What the framework does *not* claim

- Broad multi-tenant SaaS readiness
- Fully autonomous no-human operations
- Guaranteed “zero security risk”
- Production local-only LLM mode without a real local backend (`LOCAL_ONLY` fails closed today)

Honest commercial posture: **supervised pilot / managed appliance**, strong on governance and recoverability.

---

## 15. Where to read next

| Need | Document |
|---|---|
| Japanese detailed guide | [`FRAMEWORK_GUIDE_JA.md`](FRAMEWORK_GUIDE_JA.md) |
| Architecture diagram depth | [`ARCHITECTURE.md`](ARCHITECTURE.md) |
| Module inventory | [`MODULE_INVENTORY.md`](MODULE_INVENTORY.md) |
| Ready vs experimental | [`READY_VS_EXPERIMENTAL.md`](READY_VS_EXPERIMENTAL.md) |
| Transfer / SPA scope | [`TRANSFER_ONEPAGER_EN.md`](TRANSFER_ONEPAGER_EN.md) |
| Security | [`../../SECURITY.md`](../../SECURITY.md) |
| Governance | [`../../GOVERNANCE.md`](../../GOVERNANCE.md) |
| Mac mini setup | [`../../MAC_SETUP.md`](../../MAC_SETUP.md) |
| Runbook | [`../../RUNBOOK.md`](../../RUNBOOK.md) |
| Philosophy | [`../../internal_doc/PHILOSOPHY.md`](../../internal_doc/PHILOSOPHY.md) |
