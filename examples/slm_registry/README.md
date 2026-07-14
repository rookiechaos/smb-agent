# SLM registry fixtures

Reference promotion/candidate/rollback records for docs, tests, and local dry-runs.

- **Runtime state** is written to `slm/registry/` (gitignored) on the operator machine.
- **Committed fixtures** live under:
  - `fixtures/` — schema examples used by tests (`sample_eval_report.json`, etc.)
  - `candidates/`, `promotion_requests/`, `rollbacks/` — fuller promotion lifecycle samples

Do not copy runtime `slm/registry/*.json` back into source control. Export redacted
samples here only when updating documentation or fixtures.
