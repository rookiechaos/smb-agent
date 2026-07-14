# RUNBOOK.md — Mac mini Operator Runbook

The canonical long-form maintainer/operator runbook is
[`internal_doc/MAINTAINER_RUNBOOK.md`](internal_doc/MAINTAINER_RUNBOOK.md). This
file is the short Mac mini version: the default commercial workflow is local,
supervised, and does not open an output port.

Use:

- [`internal_doc/MAINTAINER_RUNBOOK.md`](internal_doc/MAINTAINER_RUNBOOK.md) for the full maintainer workflow, SLM governance chains, rollback posture, and incident handling
- [`MAC_SETUP.md`](MAC_SETUP.md) for dedicated Mac mini / MacBook environment preparation
- [`SECURITY.md`](SECURITY.md) for the agent-separation and threat-model details
- [`GOVERNANCE.md`](GOVERNANCE.md) for approval boundaries, write-permission policy, audit expectations, and release review
- [`DATA_POLICY.md`](DATA_POLICY.md) for retention windows and customer-record handling
- [`LEGAL_READINESS.md`](LEGAL_READINESS.md) for voice, sensitive-data, and legal launch boundaries
- [`JAPAN_TRUST_READINESS.md`](JAPAN_TRUST_READINESS.md) for Japan SMB trust-readiness notes and employee-impacting workflow rules
- [`internal_doc/BENCHMARKS.md`](internal_doc/BENCHMARKS.md) for current coding-LLM benchmark policy
- [`internal_doc/SAAS_HARDENING.md`](internal_doc/SAAS_HARDENING.md) for broader multi-tenant SaaS requirements
- [`internal_doc/LAUNCH_GAPS.md`](internal_doc/LAUNCH_GAPS.md) for local pre-launch gaps and remote-only checks
- [`DEPLOYMENT_READINESS.md`](DEPLOYMENT_READINESS.md) for the single-tenant Mac mini delivery checklist
- [`LAN_MONITORING.md`](LAN_MONITORING.md) for same-Wi-Fi / same-LAN monitor delivery
- [`OWNER_MONITOR_GUIDE_JA.md`](OWNER_MONITOR_GUIDE_JA.md) for the Japanese owner-facing monitor guide
- [`OWNER_MONITOR_QUICKSTART_JA.md`](OWNER_MONITOR_QUICKSTART_JA.md) for the one-page Windows handoff note in Japanese
- [`EMPLOYEE_INTERACTION.md`](EMPLOYEE_INTERACTION.md) for boss/employee/maintainer interaction boundaries

## Default Mac mini Posture

- Run from a dedicated Mac mini or supervised MacBook.
- Keep normal build/validation work CLI-only and local-file based.
- Do not start `smbagent serve-http` unless a separate hosted-runtime approval
  exists.
- Prefer overlay VPN access (`tailscale` or `wireguard`) for owner monitor and
  maintainer SSH access; treat bare LAN exposure as fallback-only.
- Keep customer workspaces on the local disk, outside iCloud Drive or synced
  folders.
- Use one customer workspace per customer; do not treat one Mac as hardened
  multi-tenant SaaS infrastructure.

Recommended `.env` posture for commercial customer work:

```bash
SMBAGENT_SUBPROCESS_ISOLATION=apple-container
SMBAGENT_APPLE_CONTAINER_CODING_IMAGE=smbagent/claude-code:latest
SMBAGENT_APPLE_CONTAINER_VALIDATION_IMAGE=smbagent/codex-validation:latest
SMBAGENT_SENSITIVE_MODE=true
SMBAGENT_ASR_BACKEND=mlx
SMBAGENT_ASR_DELETE_AUDIO_AFTER_TRANSCRIBE=true
SMBAGENT_TTS_BACKEND=none
SMBAGENT_EXTERNAL_EXECUTION_POLICY=hitl
SMBAGENT_ALLOW_UNATTENDED_EXTERNAL_WRITES=false
SMBAGENT_ALLOW_FAILURE_MEMORY_TRAINING_USE=false
SMBAGENT_VALIDATION_BACKEND=cli
SMBAGENT_HARNESS_PROFILE=opus-default
```

Current operating defaults:

- Coding runs through the `claude` CLI with `--model opus` by default
- Validation defaults to the `codex` CLI
- `SMBAGENT_VALIDATION_BACKEND=api` is opt-in, not the default
- Voice ASR defaults to local `mlx-whisper`; set `SMBAGENT_ASR_BACKEND=none` for text-only or `api` for cloud Whisper
- Use `smbagent voice-transcribe` for one local Mac microphone capture; use `smbagent negotiate --voice` for ASR-backed intake
- TTS is disabled by default; `SMBAGENT_TTS_BACKEND=macos` enables local macOS `say`
- External Mac mini microphones are supported through the macOS selected input
  device. Select the mic in System Settings > Sound > Input and grant Terminal
  microphone permission before using `voice-transcribe` or `negotiate --voice`
- TTS uses the macOS selected output device; it does not use the microphone
- Sensitive customers should use `SMBAGENT_SENSITIVE_MODE=true`; `SMBAGENT_LOCAL_ONLY_MODE=true` intentionally fails readiness until a real local LLM backend exists
- Claude and Codex should interact through public artifacts and validation feedback only
- Coding and validation share public plan-derived artifacts, but not private logs,
  memory, chain-of-thought, or Claude→Codex handoffs
- Across all five stages, shared information must stay limited to public rules,
  public artifacts, schemas, company context, tier caps, and structured feedback
- Do not create or pass private agent memory, hidden reasoning, raw logs, or
  informal thinking notes between stages
- Codex validation runs from `runs/round-N/validation_snapshot/code`; with
  `SMBAGENT_SUBPROCESS_ISOLATION=apple-container`, reads are narrowed to that snapshot
- Commercial macOS operator boxes should enable `SMBAGENT_SUBPROCESS_ISOLATION=apple-container`
  and prefer Apple’s official `container` runtime over the older `sandbox-exec`
  fallback.
- For coding/validation containerization on the Mac mini, keep the container
  contract shared across coding, validation, smoke, and remote benchmark
  scaffolds so the maintainer only has one isolation posture to reason about.
  Keep the lane private:
  - no published ports
  - separate coding/validation images
  - read-only mounts for shared plan/context artifacts
  - writable mounts only for `runs/` outputs and validation snapshots
  - validation reads from the snapshot, not from raw coding logs
  - runtime secrets stay in env injection, not image layers

Container definitions are checked into:

- `containers/apple/claude-code/Containerfile`
- `containers/apple/codex-validation/Containerfile`
- `containers/apple/README.md`

To print the exact build contract for the current environment:

```bash
smbagent apple-container-plan
```

To persist the same contract as JSON for handoff:

```bash
smbagent image-contract --json-out ops/apple_container_plan.json
```
- Check customer retention status with `smbagent retention-plan <customer_id>`
- Record HITL approvals with `smbagent approval-record <customer_id> ...`
- Use canonical approval identities like `human:alice@example.com`
- For Japan SMB sensitive workflows, seed workspace trust notes with
  `smbagent japan-trust-note <customer_id>`
- Employee-impacting actions such as evaluation, payroll decisions,
  disciplinary actions, attendance disputes, employee communications, GPS
  monitoring changes, and HR policy changes are HITL
- Hosted deploys and real integration writes should pass a matching `--approval-id`
- Run local trust checks with `smbagent trust-eval <customer_id>`
- Run local launch-readiness checks with `smbagent launch-readiness`
- Run source-tree hygiene checks with `smbagent repo-hygiene` before packaging or partner handoff
- Run `smbagent pre-release-check` to combine repo hygiene with the current prioritized release queue; it also archives a formal release review under `ops/release_reviews/<timestamp>-v<version>/` and updates `release_record_manifest.json` so launch notes, pre-release checks, and future remote smoke evidence share one index
- Confirm current benchmark policy with `smbagent coding-benchmarks`
- Inspect harness profiles with `smbagent harness-profiles`
- Render a boss-facing workflow monitor with `smbagent monitor <customer_id>`
- Issue a read-only boss monitor token with `smbagent monitor-auth-issue <customer_id>`
- Prefer `/monitor-login/<customer_id>` plus HttpOnly cookie over query-token monitor URLs
- Treat non-HTTPS `SMBAGENT_MONITOR_PUBLIC_BASE_URL` as a launch warning unless the monitor is only used for short-lived troubleshooting
- Issue a narrow employee token with `smbagent employee-auth-issue <customer_id>`
- Build a maintainer-facing incident report with `smbagent maintenance <customer_id>`
- Run the local SLM acceptance chain with `smbagent slm-runtime-plan` and `smbagent slm-acceptance-checklist`
- Record per-customer SLM posture with `smbagent slm-customer-policy-show/set <customer_id>`
- Review candidate quality before any promotion with `smbagent slm-quality-gate --eval-report ...`
- Prepare the remote-machine smoke plan with `smbagent smoke-harness --out installation_acceptance.plan.json`
- Inspect adaptive loop budgets with `smbagent loop-policy <customer_id>`; `SMBAGENT_MAX_ROUNDS` is only the hard cap
- Inspect the full loop contract with `smbagent loop-engineering <customer_id>` before making tuning changes
- Confirm the owner-facing `monitor.html` and operator dashboard both reflect the same loop-control posture
- Tune remote-maintainer super parameters with `smbagent tune show/set/log`
- Run framework-owned periodic workflow checks with `smbagent workflow-check-all`
- Run GPS analysis workflows only when a supported partner pack is present on `PYTHONPATH`
- Backup before risky work with `smbagent backup <customer_id>` and restore with `smbagent restore <archive>`
- Runtime workflows may prepare drafts/analysis, but external writes remain HITL by default
- Production/customer-facing use should be supervised and reviewed by a human operator

## Normal Customer Run

```bash
smbagent doctor
smbagent launch-readiness
smbagent new <customer_id>
smbagent japan-trust-note <customer_id>   # Japan SMB sensitive-workflow baseline
smbagent qualify <customer_id> --brief "..."
smbagent run <customer_id>
smbagent monitor <customer_id>
smbagent state <customer_id>
smbagent trust-eval <customer_id>
smbagent replay <customer_id> --verify
smbagent backup <customer_id>
```

After a coding-validation run, review:

```bash
cat workspaces/<customer_id>/plan_harness_manifest.json
cat workspaces/<customer_id>/runs/round-1/harness_manifest.json
cat workspaces/<customer_id>/runs/round-1/validation_snapshot/snapshot_manifest.json
```

The manifest records harness metadata, not model thoughts.

Before any external deploy, email, calendar write, CRM write, or customer-facing
runtime exposure:

```bash
smbagent approval-record <customer_id> --action <action> --resource <resource> --reason "..."
smbagent approval-log <customer_id>
```

Use canonical operator identities like `human:alice@example.com`.

## Port-Safety Rule

The Mac mini default has no output port. These commands are not part of normal
customer build/validation:

```bash
smbagent serve-http
```

Only run a server after explicit operator approval, a documented customer need,
and a network review. Prefer generated files, tarball deploys, or operator-side
review artifacts for the default workflow.

`smbagent dashboard` and `smbagent monitor <customer_id>` only write local HTML
files and are fine for operator review; they do not start a server by
themselves. The dashboard includes known Anthropic/OpenAI token usage and
Claude/Codex CLI invocation counts from each workspace's `usage.jsonl`. CLI
token counts may remain `unknown` until the vendor CLI exposes structured usage
data. `monitor.html` is now intentionally boss-facing: the primary status is
shown as `Running`, `Waiting`, `Passed`, or `Needs attention`, with technical
details kept below that summary. It also shows estimated monthly API budget use
as a percentage of the agreed contract cap.

For the boss-facing API budget estimate, set:

```bash
export SMBAGENT_MONTHLY_API_BUDGET_JPY=30000
export SMBAGENT_USD_TO_JPY_RATE=150
```

This percentage is an estimate from known API events in `usage.jsonl`. CLI
usage and unsupported model pricing stay out of the boss-facing percentage.

If you separately approve a public status page on the Mac mini, use:

```bash
export SMBAGENT_SERVE_HOST=0.0.0.0
export SMBAGENT_SERVE_PORT=8000
export SMBAGENT_MONITOR_PUBLIC_BASE_URL=https://ops.example.com

smbagent monitor-auth-issue <customer_id>
smbagent serve-http
```

For the preferred commercial setup, the intended first deployment is:

- Mac mini stays localhost/no-port by default
- owner monitor access goes through overlay VPN (`tailscale` or `wireguard`)
- maintainer SSH access also goes through VPN
- read-only URL only
- no operator/admin token sharing

LAN-only viewing remains available only as an explicit fallback.

See [`LAN_MONITORING.md`](LAN_MONITORING.md) for the delivery checklist and
recommended wording.

That exposed route should stay read-only and customer-owner facing:

- `GET /monitor-login/<customer_id>` for the boss/customer owner sign-in page
- `POST /monitor-login/<customer_id>/logout` to clear the boss monitor cookie (the owner page now exposes a visible ログアウト button)
- `GET /monitor/<customer_id>` after the login flow stores the monitor cookie
- `GET /v1/customers/<customer_id>/maintenance` and `maintenance_report.json`
  for operator use only

When a background workflow goes wrong, SSH into the Mac mini and inspect:

```bash
smbagent maintenance <customer_id>
cat workspaces/<customer_id>/maintenance_report.json
cat workspaces/<customer_id>/workflow_monitor.json
tail -n 20 workspaces/<customer_id>/transitions.jsonl
```

If the failure pattern suggests loop or annealing changes rather than a code or
requirements bug, the remote maintainer may apply a scoped tuning update:

```bash
smbagent loop-policy <customer_id>
smbagent loop-engineering <customer_id>
smbagent tune show --customer <customer_id>
smbagent tune set --customer <customer_id> \
  --creative 0.6 \
  --convergence 0.25 \
  --stale-rounds 3 \
  --operator human:alice@example.com \
  --notes "post-incident tuning after repeated validation churn"
smbagent tune log --customer <customer_id>
```

Use per-customer tuning first. Promote a setting to the global tuning file only
after it has worked across more than one customer pattern.

## SLM maintainer chain

The SLM lane is not a free-form extra agent. It stays governed through three
explicit chains:

1. acceptance checklist:
   `smbagent slm-runtime-plan` then `smbagent slm-acceptance-checklist`
2. customer policy:
   `smbagent slm-customer-policy-show/set <customer_id>`
3. quality gate before human promotion:
   `smbagent slm-quality-gate`, `slm-candidate-from-eval`,
   `slm-promotion-approve`, `slm-promotion-reject`

The full step-by-step maintainer procedure lives in
[`internal_doc/MAINTAINER_RUNBOOK.md`](internal_doc/MAINTAINER_RUNBOOK.md).

For ongoing workflow reliability, run the framework's own periodic health check:

```bash
export SMBAGENT_WORKFLOW_CHECK_INTERVAL_MINUTES=60
smbagent workflow-check-all
```

This writes `workflow_health.json` in each due workspace. On the Mac mini, wire
that command to `launchd` so the framework keeps checking generated workflows
even when no operator is manually opening the workspace.

The maintenance report now includes semi-automatic tuning suggestions with
command hints. When repeated validation churn shows up, the report may suggest a
customer-scoped command such as raising `anneal_stale_rounds` or enabling the
bridge orchestrator.

Those tuning suggestions are also shown in the operator dashboard, but they are
not shown in the boss-facing `monitor.html`.

The operator dashboard also includes a fleet memory-analytics strip for
maintainers, showing pass rate, failure/loop totals, recommendation counts, and
copy-ready customer commands when memory analytics suggests stale-round tuning.

Generate the `launchd` plist directly with:

```bash
smbagent launchd-plist --interval-minutes 60
```

This writes `ops/launchd/com.smbagent.workflow-check.plist` plus the log
directory expected by the periodic check job.
## Portal access

The default portal posture is Mac-mini-hosted and LAN-first.

Portal files:

- `portal/index.html`
- `portal/owner.html`
- `portal/employee.html`
- `portal/operator.html`

Operational intent:

- `owner.html` is the business-facing monitor
- `employee.html` is the constrained employee entry surface
- `operator.html` is the maintainer operations surface

Delivery guidance:

1. host the portal from the dedicated customer Mac mini
2. keep owner access LAN-only by default
3. give the owner a browser URL and bookmark target
4. do not position the first portal as a free-form AI chat product
5. keep technical recovery and governance information in the operator lane

For handoff and owner-facing instructions, use:

- `LAN_PORTAL_ACCESS_JA.md`
- `OWNER_PORTAL_HANDOFF_JA.md`
