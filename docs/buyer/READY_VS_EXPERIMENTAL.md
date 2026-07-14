# Ready vs experimental

Buyer-facing summary of what is safe to sell as a **supervised pilot** today.
Internal detail: [`../../internal_doc/READY_NOW.md`](../../internal_doc/READY_NOW.md).

## Ready for supervised pilot sale

These are strong enough for demos, partner alignment, and paid pilot delivery
when a maintainer still owns setup, monitoring, approvals, and launch.

### Core framework

- Five-stage pipeline with Pydantic-validated artifacts
- Claude coding / Codex validation separation + harness manifests
- Public-artifact agent boundaries
- Formal pipeline state machine + transition replay verify
- Bounded code↔validate and humanize loops (stall, annealing, checkpoints, graduated terminals)

### Single-tenant Mac mini posture

- Per-company workspace boundary
- No inbound port by default during build/validation
- Owner / employee / runtime token separation
- Local launch-readiness / security-readiness / deployment-readiness checks
- Local-first voice posture (MLX ASR) when voice is enabled

### Governance and trust

- Approval log with action/resource matching
- HITL default for risky external actions
- Japan trust/readiness packet support
- Hashed auth token storage for current records
- Retention / data-policy scaffolding

### Observability and recovery

- Owner monitor page
- Operator dashboard / maintenance report
- Workflow health checks + launchd helper
- Failure memory / loop memory / memory analytics
- Backup / restore
- Revisioned public workspace state (OCC + reducer)

### Vertical starters

- Dental / real-estate / legal templates
- Demo Tokyo dental example

## Ready only as reference / optional

| Item | Status |
|---|---|
| Withheld partner/customer workflow pack | **Withheld** under seller `do-not-upload/` — not part of SPA |
| Local SLM advisory | Scaffolded; **off by default**; not required for pilots |
| Optional `serve-http` | Available; not the default Mac mini path |
| Game studio | Experimental |

## Not ready / do not claim

- Broad multi-tenant SaaS
- Fully autonomous AI employee
- Unattended external writes as default
- Guaranteed “no security issues”
- Self-serve PLG without operator
- Production local-only LLM mode (`SMBAGENT_LOCAL_ONLY_MODE`) — fail-closed until a real local LLM backend exists

## Safe sales wording

> A supervised, trustable AI operations backend for SMBs, delivered on a
> dedicated Mac mini, with governed workflows, monitoring, maintenance, and
> human approval at critical execution boundaries.

Short:

> One company, one Mac mini, one governed AI backend.

## Commercial bottom line

| Claim | Verdict |
|---|---|
| Supervised pilot | **Yes** |
| Managed per-company appliance | **Yes** |
| First real launch on a prepared Mac mini | **Close** — needs machine acceptance |
| Broad autonomous rollout | **No** |
