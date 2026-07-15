# Local runtime workspace data

This directory is intentionally local-only.

Generated customer/runtime artifacts such as `auth.json`, `monitor_auth.json`,
`employee_auth.json`, `operator_approvals.jsonl`, `workflow_health.json`,
`maintenance_report.json`, and rendered monitor/dashboard HTML belong here on the
operator machine, but they must not be committed as source-controlled repo content.

Use this tree for real customer execution on the dedicated Mac mini. Keep it on a
local non-synced disk, and only export redacted samples intentionally.
