# slm prompts

This folder is the prompt home for the future local SLM layer.

The intent is to keep the prompts for the embedded local planner/router small,
structured, and easy to version separately from the larger cloud-model prompts.

## Planned prompt families

- `request_router.md`
  - classify request type
  - choose workflow family
  - suggest HITL vs unattended posture

- `loop_advisor.md`
  - inspect compact loop/failure signals
  - suggest continue / stop / escalate

- `employee_router.md`
  - route employee requests to workflow / skill / maintainer buckets

- `preplan.md`
  - compress a request into a compact structured pre-plan

- `context_refresh.md`
  - detect whether company context likely needs a refresh

## Prompt style rules

- short context only
- public reasons only
- JSON-only output
- no hidden reasoning requirements
- bounded, schema-matching fields

## Current posture

These prompts are preparation artifacts only.

- no production pipeline reads them yet
- they exist so future local backends can share stable prompt text and reviews
