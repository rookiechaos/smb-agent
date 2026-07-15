# EMPLOYEE_INTERACTION.md

This document defines how three different human roles should interact with
`smbagent` in a commercial SMB deployment:

- boss / owner
- ordinary employee
- maintainer / operator

The goal is simple: keep the system easy to use without blurring authority,
permissions, or accountability.

Read this together with [`internal_doc/PHILOSOPHY.md`](internal_doc/PHILOSOPHY.md),
[`GOVERNANCE.md`](GOVERNANCE.md), [`SECURITY.md`](SECURITY.md), and
[`LAN_MONITORING.md`](LAN_MONITORING.md).

## Why this separation matters

`smbagent` is meant to become a trustable AI agent for SMB operations.

That trust does not come from one giant chat box that everyone uses with the
same permissions.

It comes from role separation:

- leaders see status and results
- employees use constrained business entry points
- maintainers handle recovery, tuning, and system control

This keeps the AI useful without turning it into an ungoverned internal actor.

## 1. Boss / owner interaction

The boss or owner should primarily use `smbagent` as a visibility surface, not
as a low-level operations console.

Recommended interaction style:

- read-only workflow monitor
- periodic review of progress and outcomes
- light confirmation that the AI is operating within budget and expectation

Typical boss-facing access:

- `monitor.html`
- `GET /monitor/<customer_id>?token=...` on the same LAN when approved

What the boss should be able to see:

- `Running / Waiting / Passed / Needs attention`
- current workflow step
- last update time
- estimated monthly API budget use as a percentage of the agreed cap

What the boss should not be given:

- SSH access
- tuning commands
- approval logs
- maintenance reports
- private agent reasoning
- raw internal logs

In product terms, the boss gets confidence and visibility, not operator power.

## 2. Ordinary employee interaction

Ordinary employees should not interact with the raw backend directly.

They should interact through narrow, purpose-built entry points that match real
work inside the company.

Recommended employee-facing formats:

- browser-based chat or form
- local voice intake
- fixed workflow request surface

Recommended access pattern in this repo:

- issue a dedicated employee token with
  `smbagent employee-auth-issue <customer_id>`
- expose only:
  - `POST /v1/customers/<customer_id>/employee/chat`
  - `GET /v1/customers/<customer_id>/employee/skills`
- do not reuse operator/runtime bearer tokens for employee access

Good examples:

- appointment change request
- daily report voice input
- customer reply draft
- internal message draft
- GPS analysis request
- review-response draft

The key idea is that the employee is not asked to understand the whole system.
They use a small business task interface, and the framework routes that request
into the governed backend.

### What employee interactions should optimize for

- clarity
- low training burden
- bounded scope
- repeatability
- low risk of accidental misuse

### What employee interactions should avoid

- unrestricted general-purpose admin chat
- direct file/system access
- direct secret handling
- direct external execution authority
- informal side-channel instructions that bypass workflow records

### Recommended employee permission boundary

Employees may:

- submit information
- ask for drafts
- request analysis
- trigger approved internal workflows

Employees should not directly:

- deploy
- send real external emails without approval flow
- change governance settings
- change model/tuning parameters
- inspect maintenance-only records

In other words, employees talk to business-facing AI entry points, not to the
maintenance substrate.

## 3. Maintainer / operator interaction

The maintainer or operator is the person responsible for reliability, recovery,
and system-level control.

This role belongs on the Mac mini side, normally over:

- local CLI
- local files
- SSH access

Typical maintainer tools include:

- `smbagent maintenance <customer_id>`
- `smbagent dashboard`
- `smbagent workflow-check-all`
- `smbagent tune show/set/log`
- `smbagent trust-eval <customer_id>`
- `smbagent backup <customer_id>`
- `smbagent auth-issue <customer_id>`
- `smbagent employee-auth-issue <customer_id>`
- `smbagent monitor-auth-issue <customer_id>`

The maintainer is allowed to:

- investigate failures
- inspect logs and artifacts
- rotate tokens
- adjust super parameters
- manage monitor exposure
- prepare rollback/recovery

The maintainer is also responsible for respecting governance:

- external writes remain HITL unless policy explicitly changes
- customer-sensitive data handling follows retention/legal rules
- operator identity should be recorded in approval and tuning logs

## Recommended product shape

For most SMB deployments, the cleanest interaction design is:

- boss: monitor
- employee: simple task entry point
- maintainer: CLI/SSH operations

That is more trustworthy than giving all three roles the same interface.

## Interaction matrix

| Role | Main interface | Purpose | Not intended for |
|---|---|---|---|
| Boss / owner | Monitor page | Visibility, confidence, progress checks | Maintenance or configuration |
| Ordinary employee | Task-specific chat / form / voice entry | Request work, provide input, receive drafts | Admin control or system tuning |
| Maintainer / operator | SSH, CLI, local artifacts | Recovery, tuning, monitoring, governance | Casual day-to-day business use |

## Design rule for future features

When adding a new feature, ask:

1. Which role is this for?
2. What is the narrowest interface that still helps that role?
3. Does it expose power that belongs to another role?

If one feature tries to act as boss dashboard, employee workspace, and
maintainer console at the same time, it is probably violating the repo's trust
model.

## Short version

`smbagent` should not be experienced as one flat AI surface for everyone.

The trustable default is:

- bosses monitor
- employees use bounded business entry points
- maintainers operate and repair the system

That role separation is part of the product, not just an implementation detail.
