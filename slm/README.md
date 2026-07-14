# slm

Canonical implementation lives in [`smbagent/slm/`](../smbagent/slm/). The
top-level `slm/` package remains as a compatibility import path for older
`from slm ...` imports; prefer `from smbagent.slm ...` in new code.

This folder is the local-inference preparation area for the future embedded SLM
layer described in [`internal_doc/FUTURE_PLAN.md`](../internal_doc/FUTURE_PLAN.md).

The current working assumption is:

- hardware: base Mac mini M4 Pro
- first local model target: `Qwen 3.5 2B`
- first deployment preference: `bf16`, conservative context length, low memory pressure
- role: routing / triage / employee routing / planning assist / loop advisory / context refresh detection
- serving direction: `sglang` preferred long-term, adapter-first in repo

This folder does **not** mean the repo already has a production local SLM
backend. It is a staging area for the contracts and artifacts that should be
stable before we wire in real local inference.

## What belongs here

- request/response schemas for the future local SLM layer
- sample JSON payloads for routing, employee routing, planning assist, context refresh, and loop advisory
- notes on `sglang` integration and fallback behavior
- later: small local prompt templates, benchmarking notes, and backend adapters

## What does not belong here yet

- hidden reasoning traces
- customer raw logs copied for training
- production secrets
- hard-wired assumption that one serving backend is final

## Planned local SLM jobs

The first target jobs are:

1. request triage
2. workflow-family suggestion
3. compact planning pre-structure
4. loop continue / stop / escalate advice
5. context refresh suggestion

All outputs should stay structured, bounded, and machine-checkable.

## Files

- [`schemas.py`](schemas.py): Python schema contract for the future local SLM layer
- [`adapter.py`](adapter.py): backend protocol, metadata, and fail-closed error contract
- [`backend_sglang.py`](backend_sglang.py): HTTP-backed local adapter for a future `sglang` service
- [`sglang_runtime.py`](sglang_runtime.py): default runtime/service scaffold for a future `sglang` + `Qwen 3.5 2B` deployment
- [`backend_stub.py`](backend_stub.py): non-functional placeholder backend for wiring and tests
- [`factory.py`](factory.py): backend selector for `stub`, future `sglang`, and future `mlx_direct`
- [`backend_sglang.md`](backend_sglang.md): how a future `sglang` backend should fit the adapter contract
- [`service_contract.md`](service_contract.md): minimal HTTP contract for the future local service
- [`mock_sglang_service.py`](mock_sglang_service.py): very-light dry-run HTTP mock for remote Mac mini acceptance work
- [`sglang_service.env.example`](sglang_service.env.example): example environment for a future local `sglang` service
- [`sglang_runtime.md`](sglang_runtime.md): how the `sglang` runtime/service layer should be shaped on the target Mac mini
- [`TRAINING_PLAN.md`](TRAINING_PLAN.md): weekly `LoRA` / adapter tuning plan with admin approval and rollback requirements
- [`training_registry.py`](training_registry.py): hard-coded schema and file-layout scaffold for candidate adapters, promotion requests, active adapter state, and rollback records
- [`specialist_dataset.py`](specialist_dataset.py): sanitized dataset/export scaffold for the future specialist routing model
- [`dataset_review.py`](dataset_review.py): very-light weekly dataset quality review for pre-LoRA human checks
- [`prompts/`](prompts/): future local SLM prompt home for request routing and loop advice
- [`sample_router_request.json`](sample_router_request.json): example triage input
- [`sample_router_response.json`](sample_router_response.json): example triage output
- [`sample_loop_advice_request.json`](sample_loop_advice_request.json): example loop-advice input
- [`sample_loop_advice_response.json`](sample_loop_advice_response.json): example loop-advice output
- [`sample_employee_route_request.json`](sample_employee_route_request.json): example employee-routing input
- [`sample_employee_route_response.json`](sample_employee_route_response.json): example employee-routing output
- [`sample_preplan_request.json`](sample_preplan_request.json): example planning-assist input
- [`sample_preplan_response.json`](sample_preplan_response.json): example planning-assist output
- [`sample_context_refresh_request.json`](sample_context_refresh_request.json): example context-refresh input
- [`sample_context_refresh_response.json`](sample_context_refresh_response.json): example context-refresh output
- [`sglang_notes.md`](sglang_notes.md): backend direction and readiness notes

## Current posture

Today this folder is preparation work only.

- no real local SLM is invoked from the main pipeline
- no local `sglang` runtime is assumed to be installed
- no production inference path depends on this folder yet

That is intentional: the contract should stabilize before the implementation is
allowed to influence production behavior.

What is now in place for `sglang`:

- an adapter contract
- an HTTP backend scaffold
- a runtime/service scaffold with default host, port, health path, and launch command shape
- copyable `.env` and launch-command snippets for Mac mini installation planning
- a conservative memory estimate for `Qwen 3.5 2B` in `bf16`
- environment-variable configuration
- fail-closed parsing and timeout behavior
- a preserved default model profile for `Qwen 3.5 2B`

What is now in place for weekly adapter governance:

- a hard-coded registry shape for candidate adapters, evaluation reports,
  promotion requests, active-adapter state, and rollback records
- CLI scaffolding for `slm-candidate-create`, `slm-candidate-from-eval`,
  `slm-promotion-approve`, `slm-promotion-reject`, `slm-rollback`,
  `slm-status`, and `slm-dataset-build`
- explicit admin approval before activation
- fast rollback back to the previous adapter version

What is still missing:

- the real local service process
- production wiring into the main pipeline
- real latency/quality benchmarking on the target Mac mini
- real training execution that produces candidate adapters and eval reports
- integration from the future training runner into the registry/admin CLI flow


What is now in place for the later specialist routing model:

- a typed label schema for future routing/assignment tuning
- a sanitized dataset snapshot builder from local public artifacts only
- dataset manifests plus `examples.jsonl` snapshots under `slm/datasets/`
- an automatic `weekly_review.json` + `weekly_review.md` so operators can sanity-check data quality before real LoRA work
- explicit governance fields so later training does not drift into hidden autonomy
- a framework-level expansion status surface (`slm-framework-status`, `ops/slm_packs/expansion.json`) for guarded rollout thresholds, per-vertical readiness, the `Qwen 3.5 4B` hold/allow decision, training automation posture, and routing-specialist readiness
