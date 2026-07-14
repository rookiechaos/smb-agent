# Local SLM Service Contract

This document defines the minimal HTTP contract expected by the future local SLM
service layer used by [`backend_sglang.py`](backend_sglang.py).

It is meant for dry runs, local mock services, and future real `sglang`
deployments on the operator Mac mini.

## Purpose

The local SLM service should provide a small, bounded inference surface for:

1. request classification / routing
2. employee request routing
3. compact planning assist
4. loop continue / stop / escalate advice
5. context-refresh detection

The service is not a general-purpose chat endpoint.

## Transport

- HTTP
- local or LAN-adjacent only by default
- JSON request body
- JSON response body
- no streaming required for V1

## Endpoints

### 1. `POST /classify_request`

Request body:

- must match [`LocalSLMRequest`](schemas.py)

Response body:

- must match [`LocalRouterDecision`](schemas.py)

### 2. `POST /advise_loop_action`

Request body:

- must match [`LocalSLMRequest`](schemas.py)

Response body:

- must match [`LoopAdviceDecision`](schemas.py)

### 3. `POST /route_employee_request`

Request body:

- must match [`LocalSLMRequest`](schemas.py)

Response body:

- must match [`EmployeeRoutingDecision`](schemas.py)

### 4. `POST /build_preplan`

Request body:

- must match [`LocalSLMRequest`](schemas.py)

Response body:

- must match [`PlanningAssistDecision`](schemas.py)

### 5. `POST /detect_context_refresh_need`

Request body:

- must match [`LocalSLMRequest`](schemas.py)

Response body:

- must match [`ContextRefreshDecision`](schemas.py)

## Required behavior

- return HTTP 200 with a JSON object on success
- return a non-200 code for service-level failure
- never return plain text as a successful payload
- never require hidden session memory
- keep latency bounded; client-side timeout defaults are expected

## Response expectations

All successful responses should:

- be valid JSON objects
- include only public reasoning
- remain schema-compatible with repo-side validators
- include confidence values

## Security / trust expectations

- local-only by default unless separately approved
- no customer raw logs copied into the service state
- no hidden memory shared across customers unless explicitly designed and reviewed
- no authority over external actions

## Dry-run use

For remote Mac mini acceptance work, the first target is not model quality but
contract integrity:

1. start a mock local service
2. point `backend_sglang.py` at it
3. verify request/response compatibility
4. verify fail-closed behavior on malformed responses

That is enough to de-risk the service shape before real local inference is
introduced.
