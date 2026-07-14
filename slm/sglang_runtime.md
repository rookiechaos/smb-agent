# sglang_runtime

This note describes the intended runtime/service frame for the local `sglang`
backend used by the embedded SLM layer.

## Default target

The default planned target is:

- serving framework: `sglang`
- local model profile: `Qwen 3.5 2B`
- deployment host: base Mac mini M4 Pro
- preferred dtype: `bfloat16`
- conservative context length: `8192`
- static memory fraction target: `0.7`

The goal is not to run a large always-on reasoning model. The goal is to run a
small local coordinator model for:

- routing / triage
- employee request routing
- compact planning assist
- loop advice
- context refresh detection

## Runtime shape

The repo now has a runtime scaffold in:

- [`sglang_runtime.py`](sglang_runtime.py)

That scaffold defines:

- host / port defaults
- endpoint defaults
- health endpoint
- a launch-command shape
- env export values for the adapter layer
- a copyable Mac mini install snippet
- a conservative memory estimate for `bf16`

## Intended first launch shape

The first runtime command shape is expected to look like:

```bash
python -m sglang.launch_server \
  --host 127.0.0.1 \
  --port 30070 \
  --model-path Qwen/Qwen3.5-2B-Instruct \
  --dtype bfloat16 \
  --context-length 8192 \
  --mem-fraction-static 0.7 \
  --tp-size 1
```

This is a planning scaffold only. The repo does not assume that `sglang` is
already installed or that this command has been validated on the target Mac.

## Memory posture

For the current default target (`Qwen 3.5 2B`, `bf16`, context `8192`), the
runtime scaffold uses a conservative estimate:

- model weights: about `4.0 GB`
- KV cache: about `1.2 GB`
- runtime overhead: about `1.5 GB`
- estimated working set: about `6.7 GB`
- recommended total budget with headroom: about `8.7 GB`

This is not a measured benchmark yet. It is a planning estimate intended to
keep the first Mac mini deployment modest and stable.

## Why this exists separately from the adapter

The adapter layer and the runtime/service layer are not the same thing:

- adapter: how the repo talks to a local service
- runtime spec: how we intend to stand up that service

Keeping them separate makes it easier to:

- preserve the `Qwen 3.5 2B` default
- swap launch flags later if `sglang` changes
- test dry-run integration without pretending the service is production-ready
