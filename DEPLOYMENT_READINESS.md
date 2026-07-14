# DEPLOYMENT_READINESS.md

This document is the partner/customer-facing deployment checklist for the
intended `smbagent` commercial posture:

- one company
- one dedicated Mac mini or MacBook operator host
- one company-scoped workflow boundary
- human approval at critical execution edges

It is not a broad multi-tenant SaaS rollout checklist. It is a
**single-tenant managed deployment** checklist.

## Pillar 1: Single-Customer Deployment Maturity

The deployment should have:

- a completed machine install checklist
- a remote maintenance playbook
- backup / restore steps
- version recording in launch notes
- formal launch acceptance

Concrete repo references:

- machine prep: [`MAC_SETUP.md`](MAC_SETUP.md)
- operator runbook: [`RUNBOOK.md`](RUNBOOK.md)
- launch gaps: [`internal_doc/LAUNCH_GAPS.md`](internal_doc/LAUNCH_GAPS.md)

Minimum commands:

```bash
smbagent doctor
smbagent launch-readiness
smbagent smoke-harness --out installation_acceptance.plan.json
smbagent backup <customer_id>
```

Operator confirmations expected in `.env` before launch:

```bash
SMBAGENT_LOCAL_WORKSPACE_CONFIRMED=true
SMBAGENT_BACKUP_RESTORE_DRILL_CONFIRMED=true
SMBAGENT_LAUNCH_ACCEPTANCE_CONFIRMED=true
```

## Pillar 2: Local Privacy Posture

The deployment should have:

- FileVault enabled
- workspaces kept on local storage
- no iCloud Drive or synced-folder workspace location
- LAN-only owner monitor by default
- sensitive-mode plus local-first voice path for higher-risk customers

Concrete repo references:

- threat model: [`SECURITY.md`](SECURITY.md)
- legal/sensitive mode: [`LEGAL_READINESS.md`](LEGAL_READINESS.md)
- LAN owner monitor: [`LAN_MONITORING.md`](LAN_MONITORING.md)

Operator confirmations expected in `.env` before launch:

```bash
SMBAGENT_FILEVAULT_CONFIRMED=true
SMBAGENT_NO_SYNCED_FOLDERS_CONFIRMED=true
SMBAGENT_MONITOR_EXPOSURE=local-only
```

Recommended baseline:

```bash
SMBAGENT_SENSITIVE_MODE=true
SMBAGENT_ASR_BACKEND=mlx
SMBAGENT_ASR_DELETE_AUDIO_AFTER_TRANSCRIBE=true
SMBAGENT_TTS_BACKEND=none
SMBAGENT_SERVE_HOST=127.0.0.1
```

## Pillar 3: Approval Governance

The deployment should have:

- clear approval actions/resources
- canonical operator identities
- owner-facing monitor/approval visibility
- append-only auditable approval logs

Concrete repo references:

- governance policy: [`GOVERNANCE.md`](GOVERNANCE.md)
- owner monitor guide: [`OWNER_MONITOR_GUIDE_JA.md`](OWNER_MONITOR_GUIDE_JA.md)
- employee/boss/maintainer boundaries: [`EMPLOYEE_INTERACTION.md`](EMPLOYEE_INTERACTION.md)

Minimum commands:

```bash
smbagent approval-record <customer_id> --action <action> --resource <resource> --reason "..."
smbagent approval-log <customer_id>
smbagent monitor-auth-issue <customer_id>
```

Expected identity style:

```text
human:alice@example.com
human:president@example.com
```

## Pillar 4: Recoverability

The deployment should have:

- boss-facing workflow monitor
- maintainer incident report
- workflow health report
- tuning suggestions
- periodic launchd checks on the Mac mini

Concrete repo references:

- operator runbook: [`RUNBOOK.md`](RUNBOOK.md)
- Mac setup / acceptance: [`MAC_SETUP.md`](MAC_SETUP.md)

Minimum commands:

```bash
smbagent monitor <customer_id>
smbagent maintenance <customer_id>
smbagent workflow-check <customer_id>
smbagent launchd-plist --interval-minutes 60
```

Maintainer-first files:

- `workflow_monitor.json`
- `maintenance_report.json`
- `workflow_health.json`
- `tuning/changes.jsonl`

## What “Ready” Means

A customer deployment is close to ready when:

- `smbagent doctor` passes
- `smbagent launch-readiness` passes except for remote-only smoke checks
- the four readiness pillars are explicitly confirmed
- launch notes record actual machine versions and operator identities
- backup/restore and monitor delivery have been rehearsed

## What Is Still Separate

This checklist does not replace:

- real remote Anthropic/OpenAI/Claude/Codex smoke testing
- customer-specific legal sign-off for clinic/payroll/GPS/employee monitoring
- contract-specific API cap / retention language

Those remain part of:

- [`internal_doc/LAUNCH_GAPS.md`](internal_doc/LAUNCH_GAPS.md)
- [`LEGAL_READINESS.md`](LEGAL_READINESS.md)
- [`PRICING.md`](PRICING.md)
