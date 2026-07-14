# Transfer one-pager (English)

**Product:** `smbagent` — the **complete** supervised AI operations framework for Japanese SMBs  
**Deal shape:** IP / codebase transfer so the buying company can commercialize and operate the product  
**Machine model:** one company · one dedicated Mac mini · human approval at critical edges

---

## What you are buying

You receive the **entire `smbagent` code framework**, not a demo slice.

That includes the full runtime and build system needed to:

1. Run the five-stage customer build pipeline: Qualify → Negotiate → Plan → Code ↔ Validate  
2. Operate governed workflows with HITL approvals, monitoring, recovery, and loop control  
3. Deliver Japan-oriented trust templates, owner monitor, role-separated portal, vertical templates, tests, and operator tooling  

This is **not** a multi-tenant ChatGPT wrapper and **not** a claim of fully autonomous AI employees.

Safe wording:

> One company, one Mac mini, one governed AI backend.

---

## Complete framework included in the transfer

| Area | Paths | What it is |
|---|---|---|
| **Core framework** | `smbagent/` | Pipeline, agents, loop engineering, governance, workspace, CLI, templates (dental / real-estate / legal), transports, monitor |
| **Local SLM scaffold** | `slm/` | Optional local advisory layer (default-off) |
| **Portal surfaces** | `portal/` | Owner / employee / operator entry HTML |
| **Japan trust templates** | `japan_trust/` | Policy / notice starters |
| **Tests** | `tests/` | Trust / governance / pipeline regression suite |
| **Containers contract** | `containers/` | Apple-container image definitions |
| **Demo** | `examples/demo-tokyo-dental/` | Sanitized end-to-end example |
| **Buyer DD pack** | `docs/buyer/` | Architecture, inventory, gaps, handoff |
| **Commercial / ops docs** | root `*.md`, `internal_doc/` | Deploy, security, governance, runbooks, roadmap |
| **Legal** | `LICENSE`, `NOTICE`, `pyproject.toml` | Apache-2.0; ownership assignment via **separate SPA** |

After install, the buyer can run the same core product path:

```bash
pip install -e ".[dev]"
smbagent doctor
smbagent new acme-dental
smbagent qualify acme-dental --brief "..."
smbagent run acme-dental
smbagent monitor acme-dental
```

---

## What is *not* the framework (SPA exclusions only)

These are **seller/partner-specific bags**, not the `smbagent` framework itself.
They live under `do-not-upload/` and are omitted from the export.

| Excluded | Why |
|---|---|
| **Seller-withheld partner/customer workflow package** | Customer/partner-specific — excluded from this SPA by agreement |
| Seller `PRICING.md` / flyer artwork | Buyer sets own commercial terms |
| Third-party brand demo assets | Not re-licensed by default |
| Seller market-positioning / pioneer internal notes | Seller-internal |
| Local IDE settings, tuning history, ops runtime DBs | Machine-local junk — not product IP |

Ask the seller for a clean archive:

```bash
./scripts/export_product_tree.sh /tmp/smbagent-transfer
```

That script copies the **full framework** and **never** copies `do-not-upload/`.

**Read the detailed framework guide next:** [`FRAMEWORK_GUIDE_EN.md`](FRAMEWORK_GUIDE_EN.md)  
**Contract exhibit:** [`SPA_SCHEDULE_OF_ASSETS_EN.md`](SPA_SCHEDULE_OF_ASSETS_EN.md)

---

## First 7 days after close

1. Read `docs/buyer/PRODUCT_OVERVIEW_JA.md` and `READY_VS_EXPERIMENTAL.md`  
2. Install on an Apple Silicon Mac mini; run `smbagent doctor` + `launch-readiness`  
3. Replace branding, support contact, and pricing  
4. Pick **one** pilot SKU from the included templates (e.g. dental)  
5. Complete Japan trust notes before any sensitive customer data  

Full checklist: `docs/buyer/HANDOFF_CHECKLIST.md`

---

## Honest limits (do not over-claim)

- Supervised **pilot** ready; broad autonomous SaaS **not** claimed  
- Real-machine smoke (`claude` / `codex` / APIs) must be completed on **your** hardware  
- Local SLM path exists but is **default-off**  
- External side effects stay **HITL** unless you deliberately change policy  

---

## Next

Technical diligence index: `docs/buyer/README.md`  
Japanese version: `docs/buyer/TRANSFER_ONEPAGER_JA.md`
