# macOS Environment Prep

This file is for preparing and accepting a dedicated `smbagent` machine on a Mac
mini or MacBook. The first half is setup-only. The formal acceptance section is
for the remote/operator machine where real Anthropic/OpenAI/Claude/Codex smoke
tests are allowed.

## Target machine

- macOS on Apple Silicon is the preferred path.
- A Mac mini is a good always-on operator box.
- A MacBook is fine for development, dry runs, and supervised customer work.

## What this setup is for

- Preparing Python, Node, `claude`, and `codex`
- Preparing a local virtualenv and `.env`
- Verifying the machine is ready with `smbagent doctor`
- Keeping Coding and Validation separated, with CLI validation as the default
- Enabling macOS filesystem isolation for Claude/Codex before customer work
- Preparing local `mlx-whisper` ASR as the default privacy-first voice backend
- Recording the final install evidence before customer launch

## Supported setup variants

### Default: API-key operator setup

Recommended for the most predictable commercial/operator workflow.

- Required:
  - `ANTHROPIC_API_KEY`
- Optional:
  - `OPENAI_API_KEY` if you use `SMBAGENT_VALIDATION_BACKEND=api`
  - `OPENAI_API_KEY` if you override voice to cloud Whisper API ASR

### Alternative: `Claude Max` + `Codex Plus`

Good for a local CLI-first workflow on a Mac mini or MacBook.

- `Claude Max` covers Claude Code terminal usage
- `Codex Plus` covers Codex subscription usage
- Still required for the full pipeline:
  - `ANTHROPIC_API_KEY` for Qualify / Negotiation / Plan
- Still optional:
  - `OPENAI_API_KEY` if you switch validation to API mode
  - `OPENAI_API_KEY` if you override voice to cloud Whisper API ASR

Important: `Claude Max` and `Codex Plus` fit the CLI parts well, but they do
not replace Anthropic API access for the planning side of this repo.

## Recommended baseline

- macOS 14 or newer
- Xcode Command Line Tools installed
- Homebrew installed
- Python 3.11 available
- Node.js 20 or newer available

## One-time machine prep

```bash
xcode-select --install
brew update
brew install python@3.11 node
```

Confirm the toolchain:

```bash
python3.11 --version
node --version
npm --version
```

## Repo-local Python environment

From the repo root:

```bash
python3.11 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -e ".[dev,voice]"
```

This installs the Python dependencies only. It does not run the pipeline.
Install `.[serve]` only if a hosted runtime has been separately approved.

## Install the model CLIs

Coding is expected to use Claude Code and validation is expected to use Codex.
Keep validation on CLI by default unless you intentionally opt into API mode.

```bash
# Choose one Claude Code install path.
#
# Recommended latest-channel native install from Anthropic
curl -fsSL https://claude.ai/install.sh | bash

# Homebrew alternative for latest-channel updates
brew install --cask claude-code@latest
```

Install Codex CLI separately using your normal team-approved method, then verify:

```bash
claude --version
claude doctor
codex --version
```

If your team uses npm distribution instead, install or upgrade with:

```bash
npm install -g @anthropic-ai/claude-code@latest
```

## Create the local env file

```bash
cp .env.example .env
```

Fill in credentials for your chosen setup. For the default API-key setup, fill in at least:

```bash
ANTHROPIC_API_KEY=...
OPENAI_API_KEY=...
SMBAGENT_VALIDATION_BACKEND=cli
SMBAGENT_CODING_CMD="claude -p --model opus --permission-mode acceptEdits"
SMBAGENT_VALIDATION_CMD="codex exec --skip-git-repo-check"
```

Notes:

- `SMBAGENT_CODING_CMD` uses Claude Code's `opus` alias so the installed CLI
  can track the latest Opus coding model/workflow available to the account.
- `SMBAGENT_VALIDATION_BACKEND=cli` keeps Codex validation in a separate CLI process.
- `SMBAGENT_VALIDATION_BACKEND=api` is available, but it is opt-in and not the default.
- If the installed Codex build expects different flags, only change `SMBAGENT_VALIDATION_CMD`.

For commercial customer work on a dedicated Mac, also set:

```bash
SMBAGENT_SUBPROCESS_ISOLATION=macos-sandbox
SMBAGENT_SENSITIVE_MODE=true
SMBAGENT_ASR_BACKEND=mlx
SMBAGENT_ASR_DELETE_AUDIO_AFTER_TRANSCRIBE=true
SMBAGENT_TTS_BACKEND=none
SMBAGENT_LOCAL_ONLY_MODE=false
SMBAGENT_DATA_RETENTION_DAYS=180
SMBAGENT_RUNTIME_LOG_RETENTION_DAYS=90
SMBAGENT_FAILURE_MEMORY_RETENTION_DAYS=365
SMBAGENT_TRANSCRIPT_RETENTION_DAYS=30
SMBAGENT_ALLOW_FAILURE_MEMORY_TRAINING_USE=false
SMBAGENT_SERVE_HOST=127.0.0.1
SMBAGENT_SERVE_PORT=8000
```

If you want the Mac mini to expose a boss-facing read-only monitor page later,
prepare this too, but do not enable it publicly until network review/approval:

```bash
SMBAGENT_MONITOR_PUBLIC_BASE_URL=https://ops.example.com
```

## Preflight checks

These checks do not start servers and do not open an output port.

```bash
source .venv/bin/activate
smbagent doctor
smbagent launch-readiness
python -m pytest tests/test_bridge_orchestrator.py tests/test_validation.py tests/test_handoff.py tests/test_timeout_paths.py tests/test_humanize.py tests/test_e2e_mocked.py
```

What good looks like:

- `ANTHROPIC_API_KEY` is present
- `OPENAI_API_KEY` is present
- `claude` is on `PATH`
- `codex` is on `PATH`
- `subprocess_isolation=macos-sandbox` if this is a commercial operator box
- `sensitive_mode=True` for clinic, payroll, GPS, employee-monitoring, or voice pilots
- `asr_backend=mlx` and raw audio deletion enabled for local voice intake
- tests pass

## Formal Installation Acceptance

Run this section only on the Mac mini / MacBook that will be used for real
operator work. This is the handoff point between "repo prepared" and "machine
ready for first customer."

### 1. Confirm real installation

Record the following in the customer/internal launch notes:

```bash
sw_vers
xcode-select -p
brew --version
python3.11 --version
node --version
npm --version
source .venv/bin/activate
python -m smbagent.cli --help
claude --version
codex --version
```

The machine should have:

- Xcode Command Line Tools
- Homebrew
- Python 3.11
- Node.js
- repo-local `.venv`
- Claude Code
- Codex CLI
- local `.env`

If remote maintenance is part of the operating model, also record who has SSH
access to the Mac mini, the intended public monitor base URL, and who is
allowed to mint or rotate owner monitor tokens.

### 2. Confirm commercial environment posture

`.env` must include:

```bash
SMBAGENT_SUBPROCESS_ISOLATION=macos-sandbox
SMBAGENT_HARNESS_PROFILE=opus-default
SMBAGENT_VALIDATION_BACKEND=cli
SMBAGENT_CODING_CMD="claude -p --model opus --permission-mode acceptEdits"
SMBAGENT_VALIDATION_CMD="codex exec --skip-git-repo-check"
SMBAGENT_EXTERNAL_EXECUTION_POLICY=hitl
SMBAGENT_ALLOW_UNATTENDED_EXTERNAL_WRITES=false
SMBAGENT_SERVE_HOST=127.0.0.1
SMBAGENT_SERVE_PORT=8000
```

Then run:

```bash
smbagent doctor
smbagent launch-readiness
smbagent harness-profiles
smbagent smoke-harness --profile opus-default --out installation_acceptance.plan.json
claude doctor
```

`smbagent launch-readiness` should pass local checks. The remote/API E2E item is
expected to remain marked as deferred until the smoke tests below are run.

If you later approve a public boss-facing monitor page, switch
`SMBAGENT_SERVE_HOST` to `0.0.0.0`, set
`SMBAGENT_MONITOR_PUBLIC_BASE_URL`, mint a token with
`smbagent monitor-auth-issue <customer_id>`, and share only
`/monitor/<customer_id>?token=...`. Maintenance remains SSH/operator side
through `smbagent maintenance <customer_id>`.

For periodic self-check on the Mac mini, generate the scheduler file:

```bash
smbagent launchd-plist --interval-minutes 60
```

That writes `ops/launchd/com.smbagent.workflow-check.plist`. To install it on
the real Mac mini later:

```bash
cp ops/launchd/com.smbagent.workflow-check.plist ~/Library/LaunchAgents/
launchctl load -w ~/Library/LaunchAgents/com.smbagent.workflow-check.plist
```

This job runs `python -m smbagent.cli workflow-check-all` from the repo's
`.venv`, writing logs under `ops/logs/`.

### 3. Real API and CLI smoke tests

These tests intentionally use real credentials and real vendor tools. Run them
only on the approved operator machine, never during packaging or local dry
review.

Required smoke tests:

- Anthropic SDK smoke call
- OpenAI SDK smoke call, if `OPENAI_API_KEY` is configured or OpenAI-backed
  features are enabled
- Claude Code CLI smoke call
- Codex CLI smoke call

Run them through:

```bash
smbagent smoke-harness --profile opus-default --real --out installation_acceptance.json
```

This command does not open an output port and does not use customer data. It
does call configured vendor APIs/CLIs, so run it only on the approved operator
machine.

Record:

- command run
- timestamp
- operator identity
- `claude --version`
- `codex --version`
- pass/fail result
- any config override such as `SMBAGENT_CODING_CMD` or `SMBAGENT_VALIDATION_CMD`

### 4. Fake customer full pipeline dry-run

Before a real customer, run one fake customer through the complete pipeline:

```bash
smbagent new dry-run-01
smbagent qualify dry-run-01 --brief "Tokyo dental clinic, 8 staff, AI booking + FAQ"
smbagent negotiate dry-run-01
smbagent run dry-run-01
smbagent state dry-run-01
smbagent replay dry-run-01 --verify
smbagent trust-eval dry-run-01
smbagent retention-plan dry-run-01
smbagent backup dry-run-01
```

Acceptance criteria:

- pipeline reaches `PASSED`
- replay verification passes
- trust evaluation has no critical launch blockers
- retention plan is visible and reasonable
- backup archive is created
- no server command was run
- no customer data was used

### 5. Customer launch notes

Before each first real customer launch, create a launch note containing:

- customer ID
- operator identity, using canonical form such as `human:alice@example.com`
- date/time of launch approval
- retention windows for requirements, transcripts, runtime logs, failure memory,
  loop memory, backups, and approval logs
- whether [`LEGAL_READINESS.md`](LEGAL_READINESS.md) is required and completed
- whether voice is text-only, local MLX ASR, or cloud ASR
- whether TTS is disabled or local macOS `say`
- approval identity used for any deploy/email/calendar/CRM action
- backup command and restore command tested or scheduled
- `claude --version` and `codex --version`
- Anthropic/OpenAI/Claude/Codex smoke-test result references
- `installation_acceptance.json`
- latest `harness_manifest.json` path for the fake customer dry-run

Do not proceed with real customer data until this note exists.

## Mac mini notes

- Prefer a dedicated non-admin operator account if this machine is customer-facing.
- Keep the repo and workspaces on the internal SSD, not on iCloud Drive.
- Disable sleep for long supervised sessions if you expect multi-round runs.
- For external microphones, select the USB/Bluetooth/audio-interface mic in
  System Settings > Sound > Input. The ASR capture helper uses macOS `afrecord`,
  so it records from the currently selected system input device.
- Grant microphone permission to Terminal/iTerm before using voice intake.
- Optional TTS uses macOS `say` and plays through the currently selected system
  output device.
- If this machine will be shared across customers, treat it as an operator workstation, not as a hardened multi-tenant box.
- Use `smbagent voice-transcribe` for one local microphone capture and
  `smbagent negotiate --voice` for local ASR-backed intake.
- Keep `SMBAGENT_LOCAL_ONLY_MODE=false` until a real local LLM backend is
  integrated; current local-only readiness checks intentionally fail closed.

## MacBook notes

- Good for development and supervised launches.
- Avoid running long unattended sessions on battery.
- If you move between networks often, re-run `smbagent doctor` before customer work.

## Separation guidance

- Coding uses `claude` as its own subprocess in `code/`.
- Validation uses `codex` as its own subprocess by default.
- The bridge between them should stay file-based and sanitized.
- Do not switch to API validation unless you explicitly want that tradeoff.
- On customer data, keep `SMBAGENT_SUBPROCESS_ISOLATION=macos-sandbox` enabled.

## Not part of setup

These are intentionally out of scope for this file:

- starting the HTTP server
- changing tier logic
- changing coding or validation prompts
