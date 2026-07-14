# backend_sglang

This note describes how a future `sglang` backend should fit the local SLM
adapter contract.

## Intended role

The future `sglang` backend should implement the adapter contract in
[`adapter.py`](adapter.py), not create a parallel contract.

That means it should expose at least:

- `classify_request(request)`
- `advise_loop_action(request)`

and return:

- `RouterResult`
- `LoopAdviceResult`

with schema-validated decisions.

The repo now includes a scaffold implementation in
[`backend_sglang.py`](backend_sglang.py). That scaffold is configuration- and
parse-complete, but still assumes a separately managed local HTTP service.

The repo now also includes a runtime/service scaffold in
[`sglang_runtime.py`](sglang_runtime.py), with `Qwen 3.5 2B` as the default
planned model profile.

## First integration shape

The first implementation should likely:

1. accept a `LocalSLMRequest`
2. build a small bounded prompt
3. call a local `sglang` HTTP endpoint
4. parse JSON only
5. validate into the repo schemas
6. fail closed on timeout or parse problems

## Required behavior

- explicit timeout
- explicit backend/model metadata
- no silent fallback to unvalidated text
- confidence required in the output payload
- public reasons only, not hidden reasoning traces

## Non-goals for V1

- no streaming requirement
- no hidden session memory
- no direct access to customer raw logs
- no direct authority over external writes

## Readiness questions before implementation

- Is the chosen `sglang` setup stable enough on the target Mac mini?
- Is JSON-only structured generation reliable enough on the chosen small model?
- Is latency acceptable for routing/loop-advice use?
- Can backend/model/version information be recorded cleanly for observability?

Until those are answered, `backend_stub.py` should remain the default code
placeholder.
