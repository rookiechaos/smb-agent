# SGLang notes

This note records the current intended role of `sglang` in the future local SLM
stack.

## Direction

The repo should prefer:

1. an internal inference contract first
2. a pluggable local backend second
3. `sglang` as the preferred long-term serving/runtime target

## Why not hard-wire it immediately

- Apple Silicon support should be treated as a readiness item, not as a hidden
  permanent assumption
- the repo may need a direct local fallback path during the first prototype
  stage
- the schema and observability contract matter more than the first backend

## What the first backend must support

- bounded JSON output
- timeout handling
- low-latency small-model routing on a base Mac mini M4 Pro
- explicit model/version capture for observability
- fail-closed behavior when parsing or confidence thresholds fail

## First target model

- `Qwen 3.5 2B`

This is now preserved in code as the default local model profile, rather than
just being a note in docs.

## Recommended first usage

- request triage
- workflow-family suggestion
- loop continue/stop/escalate advice

## Not the first usage

- final approval authority
- coding replacement
- final validation replacement
- unattended external execution judgment
