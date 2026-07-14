# Buyer due-diligence package（買収・譲渡向け）

This folder is the **first stop for a Japanese company acquiring `smbagent`**.

**Transfer scope in one sentence:** the buyer receives the **complete `smbagent` code framework** (pipeline, agents, governance, portal, templates, tests, docs, tooling). Seller/partner-only materials under `do-not-upload/` (seller pricing, third-party brand demos, withheld partner/customer workflow packs) are excluded from the SPA archive — they are **not** “missing framework.”

## Start here

| Read order | Document | Purpose |
|---|---|---|
| 0 | [TRANSFER_ONEPAGER_JA.md](TRANSFER_ONEPAGER_JA.md) / [TRANSFER_ONEPAGER_EN.md](TRANSFER_ONEPAGER_EN.md) | Transfer one-pager — **full framework** / 譲渡ワンページ |
| 0b | [SPA_SCHEDULE_OF_ASSETS_JA.md](SPA_SCHEDULE_OF_ASSETS_JA.md) / [SPA_SCHEDULE_OF_ASSETS_EN.md](SPA_SCHEDULE_OF_ASSETS_EN.md) | **SPA 資産表（契約別紙）** |
| 1 | [FRAMEWORK_GUIDE_JA.md](FRAMEWORK_GUIDE_JA.md) / [FRAMEWORK_GUIDE_EN.md](FRAMEWORK_GUIDE_EN.md) | **コード全体の詳細紹介**（日／英） |
| 2 | [PRODUCT_OVERVIEW_JA.md](PRODUCT_OVERVIEW_JA.md) | 製品とは何か（日本語・短め） |
| 3 | [ARCHITECTURE.md](ARCHITECTURE.md) | System shape and data flow |
| 4 | [MODULE_INVENTORY.md](MODULE_INVENTORY.md) | Core vs optional vs experimental |
| 5 | [READY_VS_EXPERIMENTAL.md](READY_VS_EXPERIMENTAL.md) | What you can sell as pilot today |
| 6 | [KNOWN_GAPS.md](KNOWN_GAPS.md) | Honest launch / acceptance gaps |
| 7 | [HANDOFF_CHECKLIST.md](HANDOFF_CHECKLIST.md) | IP transfer + machine acceptance |
| 8 | [EXPORT.md](EXPORT.md) | How to package a clean tree for transfer |
| — | [LANGUAGE_POLICY.md](LANGUAGE_POLICY.md) | English + Japanese only |

Seller-only materials live in repo-root `do-not-upload/` and are **never**
copied by the export script.

## Related commercial docs (repo root)

- Product intro (EN): [`../../INTRODUCTION.md`](../../INTRODUCTION.md)
- Sales one-pager (JA): [`../../SALES_ONEPAGER_JA.md`](../../SALES_ONEPAGER_JA.md)
- Customer explanation (JA): [`../../CUSTOMER_EXPLANATION_JA.md`](../../CUSTOMER_EXPLANATION_JA.md)
- Deployment checklist: [`../../DEPLOYMENT_READINESS.md`](../../DEPLOYMENT_READINESS.md)
- Japan trust: [`../../JAPAN_TRUST_READINESS.md`](../../JAPAN_TRUST_READINESS.md)
- Governance / HITL: [`../../GOVERNANCE.md`](../../GOVERNANCE.md)

## Safe commercial wording

> A supervised, trustable AI operations backend for SMBs, delivered on a
> dedicated Mac mini, with governed workflows, monitoring, and human approval
> at critical execution boundaries.

Short:

> One company, one Mac mini, one governed AI backend.

## What this sale includes by default

**The complete `smbagent` framework:**

- `smbagent/` — full core (pipeline, agents, loops, governance, CLI, templates, transports, monitor)
- `slm/` — optional local SLM scaffolding (default-off)
- `portal/` — role-separated Japanese portal surfaces
- `japan_trust/` — Japan SMB trust templates
- `containers/` — Apple container contracts
- `examples/demo-tokyo-dental/` — sanitized demo workspace shape
- Root commercial / deployment / security docs + `internal_doc/`
- Tests under `tests/`
- Buyer DD under `docs/buyer/`

## Explicitly excluded from SPA (`do-not-upload/`) — not “missing framework”

- **Withheld partner/customer workflow packs** — SPA exclusion (seller `do-not-upload/` only)
- Seller pricing card, flyer artwork, partner-brand demo assets
- Seller market-positioning / pioneer operator notes
- Local IDE settings, tuning history, ops runtime DBs

Industry pilots after close should use `smbagent/templates/` (dental / real-estate / legal) included in the framework.

## Legal note

Software is licensed under Apache-2.0 (`LICENSE` / `NOTICE`). **Commercial
ownership transfer** (copyright assignment, trademarks, customer pipeline,
pricing rights) must be covered by a **separate IP assignment / SPA**, not by
this folder alone.
