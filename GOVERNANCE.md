# GOVERNANCE.md

This document defines the minimum governance rules for running `smbagent` with
real SMB customer work.

It is intentionally lightweight. The goal is not bureaucracy. The goal is to
make strong write/edit permissions survivable in a commercial setting.

Read this together with [`SECURITY.md`](SECURITY.md), [`DATA_POLICY.md`](DATA_POLICY.md),
[`JAPAN_TRUST_READINESS.md`](JAPAN_TRUST_READINESS.md), and [`internal_doc/LAUNCH.md`](internal_doc/LAUNCH.md).

## Why governance exists here

`smbagent` can invoke coding and validation agents that edit files and produce
customer deliverables. Even when the artifact shape is narrow, strong file-write
permissions create operational risk unless we define:

- where the agents may write
- which actions are allowed automatically
- which actions require human approval
- what gets logged
- how to recover from a bad run

## Operating principle

Treat `smbagent` as a **supervised operator backend**.

- Agents may automate constrained build work.
- Humans remain accountable for approvals, deployment, secrets, and customer-facing release.
- Production use should assume review, auditability, and rollback are required.

## Trustable Agent Principle

This repo is explicitly trying to become a **trustable AI agent system**.

That means:

- fewer directions can be acceptable
- higher autonomy can be acceptable
- but trust must come from governance, isolation, observability, and recovery

It does **not** mean "maximum autonomy wherever Docker exists."

In this repo, the trustable default is:

- unattended lane for analysis, planning, drafting, and validation inside the workspace
- HITL lane for external write operations and real-world execution

Code-level defaults reflect this:

- `SMBAGENT_TRUST_PRINCIPLE=trustable`
- `SMBAGENT_EXTERNAL_EXECUTION_POLICY=hitl`
- `SMBAGENT_ALLOW_UNATTENDED_EXTERNAL_WRITES=false`

## Permission model

### Allowed by default

These actions are acceptable without extra approval during a normal build run:

- reading and writing inside `workspaces/<customer_id>/`
- generating or updating:
  - `plan.md`
  - `tasks.json`
  - `code/`
  - `runs/round-*/*`
  - `failure_memory.jsonl`
  - `transitions.jsonl`
- reading repo-local prompts and templates needed for the build
- running the configured coding and validation toolchain for that workspace

### Not allowed by default

These actions should not happen automatically:

- writing outside the repo or outside the active customer workspace
- editing `.env`, secret stores, auth tokens, or operator credentials
- modifying deployment credentials or cloud account settings
- destructive cleanup of customer workspaces without explicit operator intent
- package installation during customer runs
- arbitrary networked side effects not already part of the approved model/API path

## Approval boundary

The following actions require explicit human approval before execution:

- deleting files or directories in a workspace
- changing auth, token, or permission logic
- changing billing-related behavior
- changing server, deployment, networking, or integration credentials
- switching validation backend for production use
- changing prompts or core agent behavior during an active customer incident
- running with broadened filesystem access beyond the normal workspace scope

For Japan-facing SMB customers, employee-impacting actions are also always
human-owned:

- employee evaluation
- payroll or compensation decisions
- disciplinary actions
- attendance disputes
- official employee communication
- GPS monitoring policy or analysis changes
- HR policy changes

When in doubt, escalate to operator approval.

## Environment separation

Use different expectations for different environments.

### Development

- Broad experimentation is acceptable.
- Local CLI workflows are fine.
- Synthetic or redacted data only.

### Staging / dry-run

- Use the same config shape intended for production where possible.
- Exercise approval and rollback paths before real customer work.
- Prefer a dedicated operator machine.

### Production / customer delivery

- Supervised runs only
- Human review before customer-facing release
- Dedicated operator environment strongly preferred
- No ad hoc prompt/config changes without recording why

## Audit and recordkeeping

Every meaningful run should leave a trace.

Minimum audit trail:

- who triggered the run
- which customer workspace was affected
- when the run happened
- which backend/tool path was used
- which files changed
- whether the run passed, failed, timed out, or halted on tooling

Current repo-level records that support this:

- `transitions.jsonl`
- `failure_memory.jsonl`
- `operator_approvals.jsonl`
- `runs/round-*/`
- `runtime/chat.jsonl`
- `runtime/workflows.jsonl`

The operator approval log is append-only and records both decisions and approval
use events. Use it for actions like deploy, real email send, calendar booking,
rollback, credential rotation, and manual overrides.

## Operator identity standard

Approval records should use canonical operator identities:

- `human:<email-or-name>` for people, e.g. `human:alice@example.com`
- `system:<service-name>` for automated internal systems, e.g. `system:release-bot`
- `service:<service-name>` for external service principals

The CLI normalizes bare values like `alice` into `human:alice`, but production
operators should prefer explicit identities. This keeps approval logs useful
when multiple operators or customer environments are involved.

Example:

```bash
smbagent approval-record acme-dental \
  --action deploy \
  --resource target=vercel \
  --operator human:alice@example.com \
  --reason "Customer approved production launch"

smbagent deploy acme-dental --target vercel --approval-id <approval-id>
```

Approvals are resource-specific and one-time by default. If an approval does
not match the requested action/resource, or has already been used, governance
blocks the command.

## Logging and retention

Prefer structured logs over raw transcripts when possible.

- Keep customer message content out of general-purpose logs unless there is a specific approved reason.
- Treat `requirements.json`, transcripts, logs, and failure memory as operational records.
- Define a retention window before customer launch. The repo-level baseline is
  in [`DATA_POLICY.md`](DATA_POLICY.md), and `smbagent retention-plan <id>`
  reports expired records without deleting them.
- If failure memory or run traces will later be used for tuning or training,
  document that internally and review it against customer contracts.

## Runtime workflow rule

The runtime workflow executor is allowed to queue and execute unattended
drafting, analysis, and notification-preparation tasks.

It must not perform external writes directly:

- real email sending
- calendar booking
- CRM mutations
- deployments
- HR/pay/disciplinary decisions

Those remain in the HITL lane unless the operator has explicitly changed the
governance policy and recorded why.

## Japan SMB trust records

For Japan-facing SMB pilots, especially clinics, payroll, GPS, voice intake, or
employee-monitoring workflows, each customer workspace should have a small
trust-readiness packet before real data is ingested:

```bash
smbagent japan-trust-note <customer_id>
smbagent trust-eval <customer_id>
```

The packet records the AI purpose of use, data categories, employee notice
status, retention window, operator identity, external provider exposure, and
HITL boundary. It is intentionally lightweight, but it gives the operator and
customer a shared record of what the AI system is allowed to do.

## Rollback and recovery

Strong write permissions are acceptable only if recovery is practical.

Minimum recovery posture:

- preserve round-by-round artifacts
- preserve verdicts and feedback
- never silently rewrite history logs
- keep enough trace to inspect what changed before redeploying

Before customer launch, operators should know:

- how to stop a bad run
- how to inspect the last changed files
- how to revert or discard a workspace state
- how to re-run from a known-good point

## Release rule

No customer-facing release should happen solely because the agent run completed.

Minimum release gate:

1. validation passed
2. structural checks passed
3. human operator reviewed the deliverable
4. any secrets/integration wiring was done manually and intentionally

## Model and prompt changes

Treat these as governed changes, not casual edits.

- record why the change was made
- record whether it is global or customer-specific
- prefer staged validation before applying it to customer work
- keep prompt changes and tuning changes attributable

For iteration/super-parameter tuning, the remote maintainer should use a named
operator identity and leave a short reason:

```bash
smbagent tune set --customer acme-dental \
  --creative 0.6 \
  --stale-rounds 3 \
  --operator human:alice@example.com \
  --notes "reduce repeated coding/validation churn after maintenance review"
```

The repo records these changes in `tuning/changes.jsonl`. Treat that file as an
append-only operational audit trail.

This is especially important if you later train a routing or task-assignment model from run history.

## Recommended minimum policy for SMB delivery

If you need a very short policy, use this:

- write access only inside the active customer workspace
- no automatic edits to secrets, auth, deploy, or billing paths
- destructive actions require human approval
- all runs leave an audit trail
- all production runs are supervised
- all customer-facing releases require human review

That is enough to be a real governance baseline without turning the repo into process theater.
