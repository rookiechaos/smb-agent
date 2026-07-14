# Known gaps (honest)

This list is for buyer due diligence. It does **not** mean the product is
unsellable — it means acceptance and first-customer work still require operator
discipline.

Source trackers:

- [`../../internal_doc/LAUNCH_GAPS.md`](../../internal_doc/LAUNCH_GAPS.md)
- [`../../internal_doc/READY_NOW.md`](../../internal_doc/READY_NOW.md)

## A. Must complete on the buyer’s Mac mini before first customer

- Formal install: Xcode CLT, Homebrew, Python 3.11, Node, venv, Claude Code, Codex CLI, `.env`, FileVault
- `smbagent doctor`
- `smbagent launch-readiness`
- `smbagent security-readiness`
- Record `claude --version` and `codex --version`
- `smbagent smoke-harness --out installation_acceptance.plan.json`
- On the approved machine only: `smbagent smoke-harness --real ...`
- Enable `SMBAGENT_SUBPROCESS_ISOLATION=apple-container` (recommended)
- Confirm `.env` stays local; never commit secrets
- Backup/restore drill: `smbagent backup` / `smbagent restore`

## B. Per-customer before sensitive data

- Customer-specific retention and contract language
- `smbagent japan-trust-note <customer_id>`
- Complete [`../../LEGAL_READINESS.md`](../../LEGAL_READINESS.md) for clinic / payroll / GPS / employee / voice cases
- Decide monitor exposure: local-only vs LAN-only vs approved public URL
- Canonical approval identities (`human:name@company.example`)

## C. Product / engineering gaps (non-blocking for supervised pilot)

| Gap | Impact |
|---|---|
| Real remote API/CLI smoke not proven in this working tree alone | Need machine evidence |
| Managed secret storage (`macos_keychain`) needs per-machine provisioning | Config exists; ops rollout remains |
| Local SLM default-off; training/inference productization incomplete | Do not sell as “local LLM first” yet |
| `SMBAGENT_LOCAL_ONLY_MODE` intentionally fail-closed | No hidden autonomy path |
| Legacy `integrations_runtime` shim still present | Prefer `smbagent.transports` |
| Historical product-shape notes in older changelog wording | Neutralized; SPA disclosure covers any residual third-party name mention |
| Root `PRICING.md` | **Buyer-must-replace placeholder** — seller rate card is under `do-not-upload/` |
| Partner demo / withheld partner workflow packs | **SPA excluded** — retained by seller under `do-not-upload/` |

## D. Packaging hygiene (before transfer archive)

- Exclude `.venv/`, caches, `__pycache__/`, `.DS_Store`
- Exclude local `ops/fleet_state.json`, `ops/slm_framework_status.json`, `ops/runtime/`
- Exclude `tuning/changes.jsonl`, `tuning/iteration.json`
- Scrub any real customer workspaces (ship tree should only have placeholders)
- See [EXPORT.md](EXPORT.md)

## E. What is already strong

- Governance / HITL defaults
- Japan trust documentation set
- Owner monitor + role-separated portal story
- Loop engineering (bounded stop/escalate/checkpoint)
- Local readiness commands and trust regression suite wiring

## Bottom line for SPA / diligence language

Safe:

> Production-minded supervised pilot framework with strong governance and
> observability; first-customer launch requires machine acceptance and
> customer-specific legal review.

Unsafe:

> Turnkey autonomous SaaS with zero remaining risk.
