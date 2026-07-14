# SLM Training Plan

This document defines the intended training loop for the future local SLM
layer.

The first version is deliberately conservative:

- model family: `Qwen 3.5 2B`
- deployment target: company-dedicated Mac mini M4 Pro
- serving posture: local inference
- tuning posture: small, periodic `LoRA` / adapter refresh
- authority posture: advisory only

The goal is not to create a fully autonomous business model. The goal is to
make the local SLM better at bounded support tasks such as routing, planning
assist, loop advice, and context-refresh detection.

## Scope of what may be tuned

The local SLM may be tuned to improve:

1. request triage
2. workflow-family routing
3. employee request routing
4. compact planning pre-structure
5. loop continue / stop / escalate advice
6. context refresh suggestion

The local SLM should **not** be tuned to become the final authority for:

- external execution
- approval decisions
- payroll or HR conclusions
- clinic or employee-impacting judgments
- hidden reasoning replacement for the main governed pipeline

## Weekly training cadence

The intended cadence is:

1. During the week:
   - collect structured runtime records
   - collect structured outcomes
   - collect failure and escalation signals

2. On a quiet night each week:
   - export a sanitized training dataset
   - train a new `LoRA` / adapter candidate
   - run holdout evaluation
   - produce an evaluation report

3. After evaluation:
   - do **not** auto-promote
   - wait for admin review and explicit approval

4. After admin approval:
   - promote the candidate adapter to active
   - keep the previous adapter version available for immediate rollback

## Recommended tuning mode

For the current Mac mini target, the preferred training path is:

- `LoRA` or `QLoRA`
- small, periodic adapter updates
- narrow task-specific tuning

The current plan is **not** full fine-tuning.

Approximate planning ranges:

- inference-only working set: about `6.7 GB`
- inference budget with headroom: about `8.7 GB`
- `LoRA` / adapter tuning: roughly `12-16 GB` planning budget
- `QLoRA`: roughly `8-12 GB` planning budget

These are planning estimates, not final measured benchmarks.

## Training data sources

The preferred sources are structured operational records already produced by
the repo.

Candidate sources:

- `failure_memory.jsonl`
- `loop_memory.jsonl`
- `transitions.jsonl`
- `maintenance_report.json`
- `workflow_health.json`
- `company_context_updates.jsonl`
- structured routing outcomes
- structured validation outcomes
- structured escalation outcomes
- tuning change history when linked to later success/failure

The preferred labels are:

- workflow family selected
- escalation needed or not needed
- maintainer/operator routing needed or not needed
- continue / stop / escalate outcome
- context refresh needed or not needed
- later success after the chosen action

## Data that must not enter training

The training export must not include:

- hidden reasoning
- raw Claude/Codex internal chain-of-thought style traces
- raw secrets or tokens
- customer data that is outside the retention/privacy policy
- raw logs that have not been sanitized for training use

The training signal should come from structured outcomes, not from hidden model
thought traces.

## Training pipeline shape

The intended weekly loop is:

1. build sanitized dataset
2. split into train / holdout
3. train candidate adapter
4. run evaluation on holdout
5. compare candidate vs current active adapter
6. write evaluation report
7. wait for admin approval
8. promote or reject

## Evaluation gates

The candidate adapter should be evaluated at least on:

- routing accuracy
- employee-routing accuracy
- loop-advice usefulness
- context-refresh precision
- false-confidence rate
- unnecessary escalation rate
- missed escalation rate

The candidate should not be promoted if it gets worse on the most important
trust-sensitive measures, especially:

- higher false-confidence
- higher missed-escalation rate
- higher operator/misroute confusion

## Promotion rule

New adapters must be treated as candidates first.

Required rule:

- training completion does **not** activate the adapter
- evaluation completion does **not** activate the adapter
- only explicit admin approval activates the adapter

Recommended promotion flow:

1. create `candidate_adapter`
2. write `eval_report`
3. write `promotion_request`
4. wait for admin approval
5. if approved, switch active adapter version
6. if rejected, keep current active adapter

## Admin approval requirement

Promotion of a new adapter should require an explicit operator/admin decision.

That approval should record:

- who approved
- when they approved
- which candidate version was approved
- which previous version was active
- why the candidate was promoted
- where the evaluation report lives

This should match the broader repo philosophy:

- strong actions are governed
- promotion is explicit
- state changes are auditable

## Rollback requirement

Rollback should be fast and boring.

The system should keep:

- the currently active adapter
- the immediately previous adapter
- the evaluation report for the promoted candidate
- a promotion record

Minimum rollback target:

- revert to previous adapter without retraining
- update the active-adapter pointer only
- preserve the failed candidate for later inspection

Recommended rollback triggers:

- worse routing accuracy in real use
- higher missed escalation
- clearly worse loop advice
- operator complaint with evidence
- trust-sensitive regression after deployment

## Versioning

Each candidate adapter should have a stable version identifier, for example:

- date stamp
- training dataset snapshot id
- model profile
- adapter generation number

Example shape:

- `qwen3.5-2b-lora-2026-06-03-r1`

The following records should exist for each candidate:

- training config
- dataset snapshot reference
- holdout evaluation report
- promotion decision
- rollback decision if applicable

## Deployment posture

The tuned adapter still lives inside the same product boundary:

- one company / one dedicated Mac mini
- local inference by default
- governed pipeline remains primary
- local SLM remains advisory

Tuning should improve the local assistant layer without weakening the human
approval and governance posture.

## First implementation target

The first practical version should be modest:

- one global adapter for SMB routing/planning-assist style tasks
- weekly night-time candidate training
- explicit admin approval before promotion
- immediate rollback to previous adapter if quality drops

Per-customer adapters can be considered later, but should not be the default
until the global training loop is stable and easy to operate.
