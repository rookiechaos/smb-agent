# smbagent

A Mac-mini-first backend for building **company-scoped AI operations systems**
for Japanese SMBs. Today it should be understood as a **supervised operator
backend** with a **single-tenant per-company deployment model**: each customer
is expected to have its own dedicated Mac mini or MacBook boundary, the system
keeps no open network port by default, prefers local voice intake, and treats
external writes as governed actions rather than automatic behavior.

It is **not yet** a full autonomous SMB workflow platform. The product goal is
a **trustable, low-direction AI agent for SMB operations**: grounded in company
context, validation, auditability, company-scoped privacy boundaries, and human
accountability where business risk becomes real.

**IP transfer / buyer due diligence:** start at [`docs/buyer/`](docs/buyer/).  
**Detailed framework intro:** [`docs/buyer/FRAMEWORK_GUIDE_EN.md`](docs/buyer/FRAMEWORK_GUIDE_EN.md) · [`docs/buyer/FRAMEWORK_GUIDE_JA.md`](docs/buyer/FRAMEWORK_GUIDE_JA.md)  
**Short intros:** [`INTRODUCTION.md`](INTRODUCTION.md) · [`INTRODUCTION_JA.md`](INTRODUCTION_JA.md)

The repo still contains a standardized customer-build mode, but that is no
longer the whole story. Today the system has two main shapes:

1. a **standardized customer build workflow** that produces a landing page,
   customer-facing skill manifests, and integration stubs
2. a **governed workflow backend** for Mac mini deployments, with company
   context, monitoring, approvals, and memory. Seller/partner-only workflow
   packs may be **withheld** from SPA transfers under `do-not-upload/`.

The recommended commercial shape is therefore **not** a broad multi-tenant SaaS
runtime. It is a **dedicated Mac mini per company**, with remote maintainer
support and human approval at critical execution boundaries.

In the standardized build mode, every customer engagement produces the same
three-artifact package:

1. **Branded landing page** (`code/landing-page/`)
2. **Customer-facing AI skills** (`code/agent-skills/` — markdown manifests)
3. **Integration stubs** (`code/integrations/` — mail, calendar, CRM)

Document boundary:

- [`docs/buyer/`](docs/buyer/) = acquisition / IP-transfer due-diligence pack
- root docs = commercial / deployment / customer-delivery materials
- [`internal_doc/`](internal_doc/) = internal strategy / roadmap / operator materials
- [`workspaces/`](workspaces/) and [`analytics/`](analytics/) = local generated runtime data only; the repo keeps placeholders there, not live customer/auth/approval/dashboard artifacts
- `do-not-upload/` = **seller-only** materials (never ship to buyers; excluded by export script)


The default five-stage build pipeline is:

**Qualify → Negotiate → Plan → Code ↔ Validate**.

---

## Mac mini Quickstart

```bash
# Install
python3.11 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev,voice]"
cp .env.example .env   # fill in credentials for your chosen setup below

# Commercial Mac mini baseline
export SMBAGENT_SUBPROCESS_ISOLATION=apple-container
export SMBAGENT_APPLE_CONTAINER_CODING_IMAGE=smbagent/claude-code:latest
export SMBAGENT_APPLE_CONTAINER_VALIDATION_IMAGE=smbagent/codex-validation:latest
export SMBAGENT_SENSITIVE_MODE=true
export SMBAGENT_ASR_BACKEND=mlx
export SMBAGENT_ASR_DELETE_AUDIO_AFTER_TRANSCRIBE=true
export SMBAGENT_TTS_BACKEND=none
export SMBAGENT_EXTERNAL_EXECUTION_POLICY=hitl
export SMBAGENT_ALLOW_UNATTENDED_EXTERNAL_WRITES=false
export SMBAGENT_ALLOW_FAILURE_MEMORY_TRAINING_USE=false
# Non-Apple-Silicon or text-only operators can set SMBAGENT_ASR_BACKEND=none.

# Verify the system is ready
smbagent doctor
smbagent launch-readiness
smbagent security-readiness

# Per-customer flow
smbagent new acme-dental
smbagent japan-trust-note acme-dental
smbagent qualify acme-dental --brief "Tokyo dental clinic, 8 staff, AI booking + FAQ"
smbagent run acme-dental         # full pipeline (negotiate → plan → code ↔ validate)
smbagent state acme-dental       # where is this customer right now?
smbagent trust-eval acme-dental
smbagent backup acme-dental
```

The default Mac mini path is CLI/local-file based and does **not** open an
inbound port during build/validation work. On current Apple Silicon operator
boxes, the preferred subprocess isolation provider is Apple's official
[`container`](https://github.com/apple/container) runtime. The framework treats
`SMBAGENT_SUBPROCESS_ISOLATION=apple-container` as the recommended Mac mini
posture; `macos-sandbox` remains a legacy fallback only.

The formal Apple-container image definitions live in:

- `containers/apple/claude-code/Containerfile`
- `containers/apple/codex-validation/Containerfile`
- `containers/apple/README.md`

Maintainers can inspect the current image contract directly with:

```bash
smbagent apple-container-plan
```

or write the same plan as JSON:

```bash
smbagent image-contract --json-out ops/apple_container_plan.json
```

When you later wire coding/validation into containerized execution, keep the
same repo contract:

- no published ports for coding/validation containers
- public artifacts only across the Coding/Validation lane
- read-only mounts for shared plan/context artifacts
- narrowly writable mounts only for run outputs and snapshots
- separate container images for Claude coding and Codex validation
- API keys injected at runtime, never baked into the image

The default Mac mini path is CLI/local-file based and does **not** open an
output port. `smbagent serve-http` is available for a separately approved hosted
runtime, but it is not part of the default commercial operator run. When remote
owner monitor access is needed, the preferred posture is overlay VPN access
(`tailscale` or `wireguard`) rather than bare LAN or public Internet exposure.

For local posture checks before customer launch, use:

- `smbagent launch-readiness`
- `smbagent deployment-readiness`
- `smbagent security-readiness`
- `smbagent repo-hygiene`
- `smbagent pre-release-check`
- `smbagent secret-list` / `secret-put` for managed SaaS credential posture
- `smbagent remote-benchmark-plan` / `remote-benchmark-record` for remote benchmark evidence capture
- `smbagent voice-redact` and `consent-record` for sensitive voice workflows
- `smbagent slm-completion-plan` for bounded local SLM completion posture

These commands are meant to reduce risk and surface gaps early. They are not a
claim that the system has zero security issues.

The framework also records filtered unsafe model outputs to
`workspaces/<customer_id>/llm_output_filter.jsonl` so operators can later see
which stages most often produced blocked responses and whether local SLM/LoRA
changes correlate with fewer such events.

By default, the framework does **not** use the local SLM for routing/allocation.
That path stays off unless you explicitly enable `SMBAGENT_ENABLE_SLM_ADVISORY=true`
and configure a local backend.

For a customer-owner status page, keep the default posture local until you have
explicit approval to expose a read-only monitor port. The intended split is:

- owner/boss view: read-only `/monitor/<customer_id>` after signing in through
  `/monitor-login/<customer_id>` with a dedicated `monitor_auth.json` token, and a visible ログアウト action clears the cookie through `/monitor-login/<customer_id>/logout`,
  with HTTPS strongly preferred for any daily owner-facing access,
  showing workflow status plus estimated monthly API
  budget usage as a percentage of the agreed cap
- employee view: constrained chat/skills endpoints with a dedicated
  `employee_auth.json` token
- maintainer view: SSH into the Mac mini and use local CLI/JSON artifacts
  including `smbagent maintenance <customer_id>`

For same-office Wi-Fi / LAN delivery, see [`LAN_MONITORING.md`](LAN_MONITORING.md).
For the customer-owner's Japanese usage guide, see
[`OWNER_MONITOR_GUIDE_JA.md`](OWNER_MONITOR_GUIDE_JA.md).
For a one-page Windows quickstart in Japanese, see
[`OWNER_MONITOR_QUICKSTART_JA.md`](OWNER_MONITOR_QUICKSTART_JA.md).
For role separation between boss, ordinary employee, and maintainer, see
[`EMPLOYEE_INTERACTION.md`](EMPLOYEE_INTERACTION.md).

Why this deployment posture matters:

- privacy is easier to explain when each company has its own machine boundary
- operational mistakes are easier to contain when customers are deployment-isolated
- human approvals remain explicit for customer-facing, employee-impacting, or
  otherwise risky actions

## Supported setups

### Default: Mac mini API-key operator setup

Recommended for commercial/operator use on a dedicated company Mac mini or
MacBook.

- Required:
  - `ANTHROPIC_API_KEY`
- Optional, depending on features:
  - `mlx-whisper` local voice deps on Apple Silicon, installed by `.[voice]`
  - `OPENAI_API_KEY` if you use `SMBAGENT_VALIDATION_BACKEND=api`
  - `OPENAI_API_KEY` if you override voice to cloud Whisper API ASR
- Typical shape:
  - Qualify / Negotiation / Plan use the Anthropic SDK
  - Coding uses `claude` CLI with the `opus` model alias by default
  - Validation defaults to `codex` CLI
  - Voice ASR defaults to local MLX on Apple Silicon
  - Customer-facing external writes are HITL-gated

This is the repo's default documented posture because it is the clearest setup
for controlled Mac-based production use.

### Alternative: `Claude Max` + `Codex Plus`

Good for a local, CLI-first operator workflow.

- `Claude Max` covers Claude Code terminal usage
- `Codex Plus` covers Codex usage with higher subscription limits
- Still required for the full pipeline:
  - `ANTHROPIC_API_KEY` for Qualify / Negotiation / Plan
- Still optional:
  - `mlx-whisper` local voice deps on Apple Silicon, installed by `.[voice]`
  - `OPENAI_API_KEY` only if you switch validation to `SMBAGENT_VALIDATION_BACKEND=api`
  - `OPENAI_API_KEY` if you override voice to cloud Whisper API ASR

Important: `Claude Max` and `Codex Plus` are not a full replacement for API
credentials in this repo. They are a good fit for the CLI parts, but the
planning side of the pipeline still needs Anthropic API access.

See [`internal_doc/LAUNCH.md`](internal_doc/LAUNCH.md) for the full operator runbook, including pre-flight
checks, real-customer launch sequence, and the rollback playbook. For dedicated
Mac mini / MacBook setup, see [`MAC_SETUP.md`](MAC_SETUP.md). For a short
entry-point alias, see [`RUNBOOK.md`](RUNBOOK.md). For failure-data analysis and
future routing-model planning, see [`internal_doc/ANALYTICS.md`](internal_doc/ANALYTICS.md). For operator
approval boundaries and write-permission policy, see [`GOVERNANCE.md`](GOVERNANCE.md). For
data retention and customer-record handling, see [`DATA_POLICY.md`](DATA_POLICY.md). For
coding-LLM benchmark policy, see [`internal_doc/BENCHMARKS.md`](internal_doc/BENCHMARKS.md). For
broader multi-tenant SaaS hardening, see [`internal_doc/SAAS_HARDENING.md`](internal_doc/SAAS_HARDENING.md). For
remaining pre-launch gaps excluding real API smoke tests, see [`internal_doc/LAUNCH_GAPS.md`](internal_doc/LAUNCH_GAPS.md). For
voice, sensitive-data, and legal launch boundaries, see [`LEGAL_READINESS.md`](LEGAL_READINESS.md). For
Japan SMB trust-readiness notes, see [`JAPAN_TRUST_READINESS.md`](JAPAN_TRUST_READINESS.md). The repo now also ships
per-customer launch-review artifacts via `smbagent customer-legal-review` and `smbagent japan-trust-launch-review`. For
commercial package structure and API cap guidance, see [`PRICING.md`](PRICING.md). For
human-role interaction boundaries, see [`EMPLOYEE_INTERACTION.md`](EMPLOYEE_INTERACTION.md). For
the product/behavior philosophy behind the repo, see [`internal_doc/PHILOSOPHY.md`](internal_doc/PHILOSOPHY.md).
For the forward roadmap that turns that philosophy into implementation phases,
see [`internal_doc/FUTURE_PLAN.md`](internal_doc/FUTURE_PLAN.md).

---

## Pipeline

```
[1] Qualify        Short LLM gate. Brief customer description → go/no-go + recommended tier.
[2] Negotiation    Japanese voice/text conversation scoped to the chosen tier's caps.
                   Output: requirements.json + transcript.txt
[3] Plan           Anthropic SDK call → standardized customer-build plan
                   (landing page + skill specs + integration specs by default).
                   Output: plan.md + tasks.json. Tier caps enforced at this layer.
[4] Coding         `claude -p --model opus` CLI in code/. Generates the planned
                   workspace artifacts against the plan.
[5] Validation     Codex validation, defaulting to `codex` CLI in a sanitized
                   validation snapshot.
                   Optional API backend via SMBAGENT_VALIDATION_BACKEND=api.
                   Independent audit vs requirements.json + tier caps.
                   Loops with [4] using an adaptive budget capped by
                   SMBAGENT_MAX_ROUNDS; halts cleanly on tooling failure.
```

All five stages are independent by design. Agents may share public rules and
public artifacts: tier caps, schemas, governance/security rules,
`requirements.json`, `company_context.json`, `plan.md`, `tasks.json`, generated
`code/`, and structured validation feedback. They must not share hidden
chain-of-thought, private model reasoning, vendor session memory, raw logs as
inputs, or private bridge summaries.

Claude coding and Codex validation have the strictest boundary. They may share
the same public plan-derived artifacts, but Codex validates from
`runs/round-N/validation_snapshot/code` and does not receive Claude logs, hidden
reasoning, memory, raw bridge summaries, or prior run history.

The post-validation humanize loop uses the `polyarch/humanize` JSON envelope
(`format: "polyarch/humanize"`, with the writer/critic payload under `payload`).

Each agent records its input + output hashes into `transitions.jsonl`, a
deterministic-replay log per customer. `smbagent replay <id> --verify` walks
the log and checks that on-disk artifacts still match what was recorded —
catches manual tampering.

---

## Deployment posture

`smbagent` is currently best treated as a **supervised Mac mini operator
backend**, not a drop-it-on-the-internet turnkey SMB platform.

The recommended commercial shape is:

- one dedicated Mac mini or MacBook operator environment
- no open inbound port during normal build/validation work
- maintainer SSH access for incident response and maintenance
- `claude` CLI for coding and `codex` CLI for validation
- `SMBAGENT_SUBPROCESS_ISOLATION=apple-container`
- local MLX ASR for voice intake when voice is used
- HITL approval for deploys, emails, calendar writes, CRM writes, and any other
  external side effect

If you later choose to expose a boss-facing status page, keep it read-only and
separate from operator/admin auth:

```bash
SMBAGENT_SERVE_HOST=0.0.0.0
SMBAGENT_SERVE_PORT=8000
SMBAGENT_MONITOR_PUBLIC_BASE_URL=https://ops.example.com

smbagent monitor-auth-issue <customer_id>
smbagent serve-http
```

That public page is meant only for status visibility. Maintenance stays on the
operator side:

```bash
smbagent maintenance <customer_id>
cat workspaces/<customer_id>/maintenance_report.json
```

Set the boss-facing API budget percentage to match the contract:

```bash
export SMBAGENT_MONTHLY_API_BUDGET_JPY=30000
export SMBAGENT_USD_TO_JPY_RATE=150
```

The monitor page shows this as an estimate based on known API usage this month.
CLI usage and any unsupported model pricing stay out of the boss summary.

The recommended first deployment shape is same-office LAN access from the
customer owner's Windows browser to the Mac mini's read-only monitor page. See
[`LAN_MONITORING.md`](LAN_MONITORING.md) for the setup and delivery checklist.

Default MLX local voice processing is a privacy improvement, not a complete
legal shield. With `SMBAGENT_ASR_BACKEND=mlx`, raw audio is intended to be
processed locally on the operator Mac. The resulting transcript and requirements
may still be sent to LLM APIs during negotiation, planning, coding, or
validation unless a separate sensitive/local-only workflow is configured. For
clinics, payroll, GPS, employee monitoring, or other sensitive work, complete
[`LEGAL_READINESS.md`](LEGAL_READINESS.md) and
[`JAPAN_TRUST_READINESS.md`](JAPAN_TRUST_READINESS.md) before using real data.
For each Japan-facing sensitive customer, seed workspace notes with:

```bash
smbagent japan-trust-note <customer_id>
```

Mac mini sensitive deployments should use:

```bash
SMBAGENT_SENSITIVE_MODE=true
SMBAGENT_ASR_BACKEND=mlx
SMBAGENT_ASR_DELETE_AUDIO_AFTER_TRANSCRIBE=true
SMBAGENT_SUBPROCESS_ISOLATION=apple-container
SMBAGENT_EXTERNAL_EXECUTION_POLICY=hitl
SMBAGENT_ALLOW_UNATTENDED_EXTERNAL_WRITES=false
SMBAGENT_ALLOW_FAILURE_MEMORY_TRAINING_USE=false
```

Voice V1 is local fixed-duration microphone capture plus ASR, not an autonomous
phone system. Use `smbagent voice-transcribe` for one local capture or
`smbagent negotiate --voice` to feed local ASR into negotiation. Optional local
spoken replies use `SMBAGENT_TTS_BACKEND=macos`; TTS is off by default.
On a Mac mini, ASR capture uses macOS `afrecord`, which records from the current
system-selected input device. External USB, Bluetooth, or audio-interface
microphones are supported as long as macOS has selected them in System Settings
> Sound > Input and Terminal has microphone permission. TTS uses macOS `say`,
which speaks through the current system-selected output device.

## Trustable Agent Principle

The repo's guiding principle is to build a **trustable AI agent**, not merely a
maximally autonomous one.

- Strong autonomy is acceptable inside the workspace for analysis, planning,
  drafting, and validation.
- Trust comes from boundaries, auditability, replayability, and recoverability,
  not just from model capability.
- External write operations should default to a human-gated lane.
- The current default posture is therefore:
  - `SMBAGENT_TRUST_PRINCIPLE=trustable`
  - `SMBAGENT_EXTERNAL_EXECUTION_POLICY=hitl`
  - `SMBAGENT_ALLOW_UNATTENDED_EXTERNAL_WRITES=false`

For Japan-facing SMBs, this principle has an extra operational meaning:

- the customer should understand the purpose of AI use
- employee, payroll, clinic, GPS, and monitoring data require documented
  launch review before real ingestion
- employee-impacting actions are always HITL
- operators should keep workspace-local evidence that policy, notice,
  retention, and approval identity were considered

## Company Context Architecture

The agent is not supposed to operate from tasks alone. Each customer should
carry a deeper company-context layer including:

- mission
- vision
- values
- current strategy
- current priorities
- decision style
- risk tolerance

This context is stored structurally and can be refreshed over time.

- initial context enters through negotiation and lands in `requirements.json`
- the current effective snapshot is written to `company_context.json`
- an operator-readable view is generated at `CONTEXT.md`
- lightweight updates append to `company_context_updates.jsonl`
- operators can refresh context without redoing the full discovery flow
- stale context warnings use `SMBAGENT_CONTEXT_REFRESH_WARN_DAYS`

- Best fit today: a dedicated Mac mini/MacBook, real pre-flight checks, CLI
  validation by default, and human review before customer-facing rollout.
- For commercial customer work, keep subprocess filesystem isolation enabled:
  `SMBAGENT_SUBPROCESS_ISOLATION=apple-container`.
- Not yet a strong default for unsupervised multi-tenant internet deployment:
  broader SaaS use still needs per-customer environment isolation, stronger
  token storage, backup automation, and production approval workflows.

Read [`SECURITY.md`](SECURITY.md) before putting customer traffic on it.

When runs fail, the pipeline now also writes append-only failure memory to
`workspaces/<customer_id>/failure_memory.jsonl`. Each row records the failed
stage, outcome, issue counts, and the effective iteration-tuning / annealing
settings active for that run so you can later compare what actually improved
pass rate or reduced loop churn.

The coding-validation loop is adaptive by default. `SMBAGENT_MAX_ROUNDS` remains
the hard safety cap, but each run gets a budget from the current coding
benchmark policy, task complexity, and recent local loop/failure memory. Outcomes
are recorded in `workspaces/<customer_id>/loop_memory.jsonl` without raw prompts
or model reasoning. Inspect a workspace's current decision with:

```bash
smbagent loop-policy <customer_id>
smbagent loop-engineering <customer_id>
```

`loop-engineering` exposes the repo's bounded-loop contract for one workspace:
stop conditions, checkpoints, learning signals, replay/branch selection, cost-aware search posture, and current tuning suggestions.
That keeps the framework closer to a supervised loop system than a one-shot
prompt or an unbounded autonomous agent.

Remote maintainers can also tune completion-rate-related super parameters over
SSH without changing the core workflow logic. The supported path is:

```bash
smbagent tune show --customer <customer_id>
smbagent tune set --customer <customer_id> \
  --creative 0.6 \
  --convergence 0.25 \
  --stale-rounds 3 \
  --operator human:alice@example.com \
  --notes "reduce repeat loop churn after maintenance review"
smbagent tune log --customer <customer_id>
```

Those changes apply on the next pipeline round. They are recorded in
`tuning/changes.jsonl` so pass-rate improvements can be compared against actual
tuning history later.

The framework can also run periodic workflow health checks over generated
customer workflows. Each check writes `workflow_health.json`, combining runtime
status plus maintenance-style issues, and sets the next due time from
`SMBAGENT_WORKFLOW_CHECK_INTERVAL_MINUTES`:

```bash
smbagent workflow-check <customer_id>
smbagent workflow-check-all
```

On a Mac mini, the intended production shape is to call `workflow-check-all`
from `launchd` or another local scheduler rather than keeping a surprise
background daemon inside the repo.

`maintenance_report.json` now also includes semi-automatic tuning suggestions
for the remote maintainer. For example, repeated validation churn or exhausted
round budgets can produce suggestions like "increase `anneal_stale_rounds`" plus
a ready-to-run `smbagent tune set ...` command hint.

You can also generate the Mac mini scheduler file directly:

```bash
smbagent launchd-plist --interval-minutes 60
```

That writes a plist under `ops/launchd/` for periodic `workflow-check-all`.

Maintainer-only tuning suggestions from `maintenance_report.json` also appear in
the operator dashboard with copy-ready command hints. They do not appear in the
boss-facing `monitor.html`.

The operator dashboard now also shows a fleet-level memory analytics summary,
surfacing pass rate, failure/loop counts, validation-backend recommendation
counts, and customer-scoped stale-round tuning suggestions derived from
`memory_analytics.json` or computed live from workspace memory.
`smbagent next-stage-summary` also emits `ops/priority_packs/loop_maturity.json`
so remote maintainers can spot which customers still have immature loop posture
and jump directly into `smbagent loop-engineering <customer_id>`.
The operator dashboard surfaces the same data as a fleet-level "Loop maturity
watchlist", so you do not need to open the JSON first.
Customers in `attention` loop posture are also pushed to the top of the
next-stage global maintainer action queue.

Harness profiles are available for Mac mini operator installs. The default is
`opus-default`; other profiles include `opus-final`, `opus-conservative`,
`sonnet-fast`, and `local-only-blocked`.

```bash
smbagent harness-profiles
smbagent smoke-harness --profile opus-default --out installation_acceptance.plan.json
```

`smoke-harness` only prints or writes a no-port plan by default. It calls real
Anthropic/OpenAI/Claude/Codex tools only when `--real` is passed on the approved
operator Mac. Every coding-validation round writes
`runs/round-N/harness_manifest.json`, recording commands, sandbox mode, prompt
hashes, code-tree digest, and events without raw prompts or private reasoning.
Plan runs also write `plan_harness_manifest.json`, and Codex validation snapshots
write `runs/round-N/validation_snapshot/snapshot_manifest.json`. These manifests
record hashes, allowed inputs, forbidden private channels, and tool configuration;
they do not store hidden reasoning.

---

## Tiers

| Tier | Monthly | Setup | Max skills | Max pages | Max integrations |
| --- | --- | --- | --- | --- | --- |
| **starter**  | $399 | $2,000 | 1 | 1 | 1 |
| **growth**   | $699 | $3,500 | 5 | 5 | 3 |
| **business** | $999 | $5,000 | 20 | 20 | 8 |

The Plan agent rejects its own output if it exceeds the customer's tier caps;
the Validation agent re-checks the counts structurally on every round, so a
misbehaving LLM cannot ship an over-tier deliverable.

---

## What's in the box

| Layer | What |
|---|---|
| **Build pipeline** | Five agents (Qualify, Negotiation, Plan, Coding, Validation), Pydantic-validated artifacts, formal state machine with explicit transitions |
| **Verticals / workflow packs** | Three template packs: dental, real-estate, legal. Seller/partner-only packs may be SPA-excluded under `do-not-upload/` |
| **Optional hosted runtime** | FastAPI server with per-customer hashed auth tokens (TTL + revocation), CORS, CSP, rate limiting, body-size limits, Prometheus `/metrics`, admin diagnose endpoints. Not started in the default Mac mini path |
| **Optional embeddable chat widget** | Vanilla JS, no deps. Drops into any page with a `<script>` tag after a separate hosted-runtime approval |
| **Voice** | Privacy-first local mlx-whisper ASR by default. Override with `SMBAGENT_ASR_BACKEND=api` for OpenAI Whisper API or `none` for text-only |
| **Integrations** | Mail (SMTP), Calendar (Google), CRM (HubSpot) — pluggable transports with in-memory test backends |
| **Safety** | Path-traversal protection on `customer_id`, structural tier-cap enforcement, regex secret-scanning across 7 provider patterns, agent-skill frontmatter validation, API-key redaction in logs |
| **Observability** | Per-customer chat JSONL (content-redacted), transition log with replay verification, `usage.jsonl` for Anthropic/OpenAI + Claude/Codex CLI usage, `memory_compaction.jsonl` for rolling-summary / packed-context / retrieval hits, `workflow_monitor.json` plus `monitor.html` for owner-visible run status, failure-memory JSONL for tuning failed runs, alert webhook, static operator dashboard, admin diagnose API |
| **Workflow execution** | Runtime workflow queue for governed drafts, analysis, and notification-prep tasks; external actions stay blocked/HITL by default |
| **Migrations** | `smbagent migrate <id>` framework. `.workspace_meta.json` stamps schema version at creation |

---

## Documentation map

Commercial/customer-facing deployment docs stay at the repo root. Internal
strategy, roadmap, benchmark, and deep operator docs now live under
[`internal_doc/`](internal_doc/).

| For | Read |
|---|---|
| **First-time setup** | This file → [`internal_doc/LAUNCH.md`](internal_doc/LAUNCH.md) pre-flight section |
| **Dedicated Mac mini / MacBook prep** | [`MAC_SETUP.md`](MAC_SETUP.md) |
| **Running smbagent in production** | [`internal_doc/LAUNCH.md`](internal_doc/LAUNCH.md) — operator runbook with daily/weekly cadence, failure modes, rollback |
| **Short runbook entry point** | [`RUNBOOK.md`](RUNBOOK.md) |
| **Operator governance / approvals** | [`GOVERNANCE.md`](GOVERNANCE.md) |
| **Data retention / compliance baseline** | [`DATA_POLICY.md`](DATA_POLICY.md) |
| **Japan SMB trust readiness** | [`JAPAN_TRUST_READINESS.md`](JAPAN_TRUST_READINESS.md) |
| **Coding-LLM benchmark policy** | [`internal_doc/BENCHMARKS.md`](internal_doc/BENCHMARKS.md) |
| **Broader SaaS hardening** | [`internal_doc/SAAS_HARDENING.md`](internal_doc/SAAS_HARDENING.md) |
| **Pre-launch local gaps** | [`internal_doc/LAUNCH_GAPS.md`](internal_doc/LAUNCH_GAPS.md) |
| **Single-tenant deployment checklist** | [`DEPLOYMENT_READINESS.md`](DEPLOYMENT_READINESS.md) |
| **Simple customer/partner introduction** | [`INTRODUCTION.md`](INTRODUCTION.md) · [`INTRODUCTION_JA.md`](INTRODUCTION_JA.md) |
| **Detailed framework guide (EN/JA)** | [`docs/buyer/FRAMEWORK_GUIDE_EN.md`](docs/buyer/FRAMEWORK_GUIDE_EN.md) · [`docs/buyer/FRAMEWORK_GUIDE_JA.md`](docs/buyer/FRAMEWORK_GUIDE_JA.md) |
| **Japanese sales flyer** | [`FLYER_JA.md`](FLYER_JA.md) |
| **Agent philosophy / product concept** | [`internal_doc/PHILOSOPHY.md`](internal_doc/PHILOSOPHY.md) |
| **Future implementation roadmap** | [`internal_doc/FUTURE_PLAN.md`](internal_doc/FUTURE_PLAN.md) |
| **Failure-data analysis / future routing model** | [`internal_doc/ANALYTICS.md`](internal_doc/ANALYTICS.md) |
| **Internal doc index** | [`internal_doc/README.md`](internal_doc/README.md) |
| **Future local SLM inference prep** | [`slm/`](slm/) |
| **Handing the system to a pioneer customer's tech lead** | Seller-only note under `do-not-upload/`; buyers use [`docs/buyer/`](docs/buyer/) |
| **Threat model + agent isolation guarantees** | [`SECURITY.md`](SECURITY.md) |
| **What changed between versions** | [`CHANGELOG.md`](CHANGELOG.md) |
| **What the standardized build mode looks like** | [`examples/demo-tokyo-dental/`](examples/demo-tokyo-dental/) |
| **First governed workflow package** | Seller may withhold partner packs under `do-not-upload/`; buyers start from `smbagent/templates/` |

---

## Selected CLI commands

| Need to | Command |
|---|---|
| Verify install is sane | `smbagent doctor` |
| Create workspace | `smbagent new <id>` |
| Seed Japan trust templates | `smbagent japan-trust-note <id>` |
| Run the full pipeline | `smbagent run <id> --brief "..."` |
| Inspect current state | `smbagent state <id>` |
| Verify no tampering | `smbagent replay <id> --verify` |
| Show data retention plan | `smbagent retention-plan <id>` |
| Run local trust evaluation | `smbagent trust-eval <id>` |
| Write the CI trust regression contract | `smbagent trust-regression-contract` |
| Run local launch-readiness checks | `smbagent launch-readiness` |
| Show coding benchmark policy | `smbagent coding-benchmarks` |
| Show harness profiles | `smbagent harness-profiles` |
| Prepare no-port smoke harness plan | `smbagent smoke-harness --out installation_acceptance.plan.json` |
| Record HITL approval | `smbagent approval-record <id> --action deploy --resource target=vercel --reason "..."` |
| Review approval log | `smbagent approval-log <id>` |
| Migrate legacy plaintext tokens | `smbagent auth-rotate-legacy` |
| Backup workspace | `smbagent backup <id>` |
| Restore workspace backup | `smbagent restore <archive.tar.gz> --customer-id <id>` |
| Render customer workflow monitor | `smbagent monitor <id>` |
| Aggregate failure/loop memory | `smbagent memory-analytics [--customer <id>]` |
| Queue safe runtime workflow | `smbagent workflow-submit <id> --kind analysis --title "..."` |
| Run next safe workflow | `smbagent workflow-run-next <id>` |
| Mint runtime token | `smbagent auth-issue <id>` |
| Deploy landing page | `smbagent deploy <id> --target vercel\|netlify\|tarball` |
| Optional HTTP server | `pip install -e ".[serve]"` then `smbagent serve-http` — uses `SMBAGENT_SERVE_HOST` / `SMBAGENT_SERVE_PORT`, opens a port, and is not part of the default Mac mini run; preferred remote posture is Tailscale/WireGuard overlay access |
| Multi-customer usage/status dashboard | `smbagent dashboard` |

For a company owner or manager, the simplest no-port monitoring surface is
`monitor.html` inside the customer's workspace. It shows whether the pipeline is
currently running, which stage is active, the latest validation verdict, queued
runtime workflows, and known model/API usage. The page auto-refreshes every 10
seconds when opened locally and presents a boss-facing summary first:
`Running`, `Waiting`, `Passed`, or `Needs attention`.
It now also exposes the loop-control posture in owner-friendly form, so the
boss can see that the AI team is bounded by explicit checkpoints, stop/escalate
conditions, artifact-based learning, and failure-memory tuning rather than an
unbounded prompt loop.
| List vertical templates | `smbagent template list` |
| Show pricing tiers | `smbagent tiers` |

`smbagent --help` for the full list. Each command has its own `--help`.

Seller/partner-only governed workflow packs may be **excluded from SPA
transfers** and retained only under `do-not-upload/`. Buyers should start from
`smbagent/templates/` and `examples/demo-tokyo-dental/`. Optional partner CLI
entry points exit with a clear error when those packs are not on `PYTHONPATH`.

---

## Completed Roadmap

The repo has already completed the first five major phases from
[`internal_doc/FUTURE_PLAN.md`](internal_doc/FUTURE_PLAN.md):

1. **Company context as product infrastructure**
   - structured `company_context`
   - `context-update`
   - generated `CONTEXT.md`
   - context freshness surfaced in status/portal/dashboard

2. **Lightweight context refresh loop**
   - periodic/event-driven context updates
   - stale-context warnings
   - configurable refresh threshold

3. **Trustable two-lane execution**
   - unattended vs HITL split
   - approval-gated external writes
   - append-only operator approval log
   - hashed runtime tokens
   - trust-eval coverage

4. **Stronger isolation**
   - Apple official `container` runtime on Mac mini
   - Linux `bwrap`
   - validation snapshots
   - role-scoped writable paths

5. **Failure memory and tuning intelligence**
   - `failure_memory.jsonl`
   - `loop_memory.jsonl`
   - adaptive loop budgets
   - `memory-analytics` JSON/CSV summaries
   - dashboard-visible tuning signals
   - memory compaction observability

Also already in place:

- boss-facing monitor views
- operator dashboard with fleet memory analytics
- commercial-readiness, repo-hygiene, and pre-release maintainer checks with archived release-review records under `ops/release_reviews/`, each indexed by `release_record_manifest.json`
- CI-backed trust/adversarial regression workflow with uploaded contract and JUnit artifacts
- Mac mini launchd generation for periodic workflow checks
- Claude/Codex separation with sanitized validation snapshots
- Japan SMB trust/readiness docs
- Partner-oriented Mac mini + n8n workflow packaging patterns

Partially completed from the commercial-readiness phase already:

- deployment / security / commercial readiness commands
- launch-note JSON and Markdown snapshots
- maintainer dashboard readiness summary
- explicit split between local blocking gaps and remote deferred gates
- source-tree hygiene checks so runtime/customer artifacts stay out of the canonical repo

## Near-term Roadmap

The next practical steps are now narrower and more concrete:

1. **Remote target acceptance on the real Mac mini**
   - real Anthropic SDK + OpenAI SDK smoke
   - real Claude CLI + Codex CLI synthetic dry-run
   - acceptance notes captured on the target machine

2. **Managed secret storage operational rollout**
   - repo code now supports the Mac-mini-first `macos_keychain` backend
   - still complete per-machine provisioning and acceptance on the real operator box

3. **Trust regression execution proof**
   - GitHub Actions wiring now runs the trust core and adversarial suites from one contract
   - next proof step is remote CI execution evidence on the real host/service

4. **Remote benchmark runner**
   - run SWE-bench Pro / LiveCodeBench / Terminal-Bench from the remote machine
   - capture cost and latency as part of release evidence

5. **Voice / sensitive-mode hardening**
   - redaction/minimization before cloud LLM calls
   - encrypted Mac mini backup flow
   - operator consent/legal UX for sensitive deployments

6. **SLM productization, still default-off**
   - local backend completion
   - acceptance checklist and customer policy wiring on the real machine
   - no hidden autonomy path or auto-promotion

## Single-Tenant Readiness Pillars

For the intended commercial posture of **one company, one dedicated Mac mini**,
the readiness story should be understood in four pillars:

1. **Single-customer deployment maturity**
   - install checklist: [`MAC_SETUP.md`](MAC_SETUP.md)
   - remote maintenance playbook: [`RUNBOOK.md`](RUNBOOK.md)
   - backup / restore: `smbagent backup <id>` and `smbagent restore <archive>`
   - version recording and launch evidence: [`MAC_SETUP.md`](MAC_SETUP.md) formal acceptance section
   - launch acceptance / smoke planning: `smbagent smoke-harness` and [`internal_doc/LAUNCH_GAPS.md`](internal_doc/LAUNCH_GAPS.md)

2. **Local privacy posture**
   - FileVault and local-only workspace guidance: [`SECURITY.md`](SECURITY.md)
   - no synced folders / local disk storage: [`RUNBOOK.md`](RUNBOOK.md)
   - LAN-only owner monitor by default: [`LAN_MONITORING.md`](LAN_MONITORING.md)
   - sensitive mode and local-first voice path: [`LEGAL_READINESS.md`](LEGAL_READINESS.md), [`MAC_SETUP.md`](MAC_SETUP.md)

3. **Approval governance**
   - clear approval actions/resources: [`GOVERNANCE.md`](GOVERNANCE.md)
   - canonical operator identity rules: `human:alice@example.com` style identities
   - owner approval/monitor view: `monitor.html` and monitor-token flow
   - auditable append-only approval logs: `smbagent approval-log <id>`

4. **Recoverability**
   - boss-facing monitor: `smbagent monitor <id>`
   - maintainer incident summary: `smbagent maintenance <id>`
   - workflow health report: `smbagent workflow-check <id>`
   - tuning suggestions: operator dashboard + `maintenance_report.json`
   - periodic self-checks: `smbagent launchd-plist --interval-minutes 60`

These pillars are largely implemented now; the remaining work is the final
remote-Mac acceptance pass and customer-specific launch/legal completion.

---

## Status

```
Version:           0.2.0
Current posture:   supervised Mac mini operator backend with live readiness and repo-hygiene checks
Primary workflow:  Qualify -> Negotiate -> Plan -> Code <-> Validate
Coding/validation: Claude Code CLI by default + Codex CLI by default
Isolation:         Apple container, Linux bwrap, validation snapshots
Trust/governance:  unattended vs HITL lanes, approval log, hashed tokens
Observability:     monitor views, operator dashboard, maintenance + memory analytics
Voice:             local MLX ASR by default on Apple Silicon; cloud ASR optional
Workflow packs:    templates + buyer-built packs; partner packs optional/withheld
```

What this means in practice:

- the repo is already strong as a governed backend for SMB operator work
- the maintainer dashboard now includes commercial readiness and pre-release check summaries
- the default deployment shape is still one dedicated Mac mini or MacBook
- LAN/read-only owner monitoring is supported
- employee, owner, and maintainer lanes are separated
- the framework supports labor, shipment/cost, and pricing/sales governance
  patterns, plus GPS analysis helpers, with n8n-oriented delivery artifacts

What is still not claimed yet:

- not yet proven end-to-end against real Anthropic + real `claude` + real
  `codex` on the final remote machine
- not yet a fully autonomous SMB workflow platform
- not yet a broad multi-tenant SaaS runtime

That first real remote-Mac smoke/acceptance pass remains the launch-blocking
step — see [`internal_doc/LAUNCH.md`](internal_doc/LAUNCH.md) §Pre-flight #3. Expect a few small CLI-flag
or JSON-shape adjustments on first contact with real APIs/CLIs.

Operationally, the safest current default is:

- a dedicated Mac mini or MacBook operator box
- no open inbound port during normal customer build work
- `claude -p --model opus` for coding, so Claude Code follows the latest Opus
  alias available to the installed account
- `codex` CLI for validation
- sanitized file-based bridge handoffs between them
- macOS sandbox isolation, local MLX voice intake, and HITL external writes

---

## Layout

```
smbagent/
├── pyproject.toml
├── README.md                ← this file
├── internal_doc/            ← internal roadmap, deep runbooks, and strategy docs
├── RUNBOOK.md               ← short runbook entry point
├── MAC_SETUP.md             ← dedicated macOS environment prep
├── SECURITY.md              ← threat model
├── DATA_POLICY.md           ← retention and data handling baseline
├── JAPAN_TRUST_READINESS.md ← Japan SMB trust-readiness checklist
├── CHANGELOG.md
├── .env.example
├── japan_trust/             ← Japan customer/employee notice templates
├── examples/
│   └── demo-tokyo-dental/   ← fully-populated sample workspace
├── smbagent/
│   ├── cli/                 ← Typer entrypoint package (split command modules)
│   ├── orchestrator.py      ← Pipeline driver + state machine + transition log
│   ├── pipeline_state.py    ← formal state enum + transition validation
│   ├── config.py            ← env-driven Config
│   ├── workspace.py         ← per-customer paths, customer_id validation
│   ├── auth.py              ← per-customer hashed runtime tokens (TTL + revocation)
│   ├── safety.py            ← structural post-checks + secret scanning
│   ├── migrations.py        ← workspace schema migration framework
│   ├── doctor.py            ← self-diagnostic checks
│   ├── agents/              ← Qualify, Negotiation, Plan, Coding, Validation
│   ├── runtime/             ← SkillsRuntime: loads agent-skills, routes via Claude
│   ├── server/              ← FastAPI: chat, admin, metrics, onboarding
│   ├── transports/          ← mail / calendar / CRM (pluggable)
│   ├── voice/               ← ASRBackend protocols + Whisper-API + mlx-whisper
│   ├── portal/              ← per-customer + multi-customer HTML views
│   ├── observability/       ← chat log + transition log + alert webhook
│   ├── deploy/              ← vercel / netlify / tarball
│   ├── templates/           ← vertical template packs
│   └── prompts/             ← every agent's system prompt
├── tests/                   ← 715 tests, zero outside ports
└── workspaces/              ← per-customer outputs (gitignored)
```

---

## License

Licensed under the [Apache License 2.0](LICENSE). See [NOTICE](NOTICE) for
attribution. Commercial ownership transfer is covered by a separate IP
assignment agreement — start with [`docs/buyer/HANDOFF_CHECKLIST.md`](docs/buyer/HANDOFF_CHECKLIST.md).

## Maintainers

Engineering ownership for a transferred copy should be updated by the buying
organization. Product handoff docs live in [`docs/buyer/`](docs/buyer/).

## Portal entry

This repo includes a lightweight portal as a unified workbench for the
single-customer Mac mini deployment.

The portal is intentionally role-based and should not be framed as a general
chat product in v1.

Main entry files:

- `portal/index.html`
- `portal/owner.html`
- `portal/employee.html`
- `portal/operator.html`

Role expectations:

- owners use the monitor view to check workflow progress, approvals, and usage
- employees use constrained entry points such as forms, uploads, and approved actions
- maintainers use the operator view for health, recovery, governance, and tuning

Default delivery model:

- the portal is hosted from the dedicated customer Mac mini
- the owner usually opens it from another machine in the same LAN
- the owner machine typically does not need a separate installation

See also:

- `portal/README.md`
- `LAN_PORTAL_ACCESS_JA.md`
- `OWNER_PORTAL_HANDOFF_JA.md`
