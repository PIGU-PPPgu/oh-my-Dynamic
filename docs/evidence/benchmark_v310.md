# oh-my-Dynamic Benchmark: repo_review_productization_v2

Run id: `benchmark_v310_real_20260607d`
Dry run: `false`
Compact JSON: `benchmark_v310.json`

## Mode Summary

| Mode | Fixtures | Passed | Failed | Avg Score | Evidence | Agents Completed | Agents Failed | Replanners | Duration |
|------|----------|--------|--------|-----------|----------|------------------|---------------|------------|----------|
| single | 5 | 0 | 5 | 0.063 | 0.012 | 0 | 5 | 0 | 300.1s |
| fixed | 5 | 0 | 5 | 0.012 | 0.012 | 0 | 25 | 0 | 300.28s |
| adaptive | 5 | 0 | 5 | 0.06 | 0.0 | 0 | 35 | 10 | 0.0s |

## Fixture Results

| Mode | Fixture | Score | Evidence | Agents | Replanners | State |
|------|---------|-------|----------|--------|------------|-------|
| single | security_command_surface | 0.113 | 0.062 | 0/1 | 0 | failed |
| fixed | security_command_surface | 0.062 | 0.062 | 0/5 | 0 | failed |
| adaptive | security_command_surface | 0.05 | 0.0 | 0/7 | 2 | failed |
| single | install_five_minute | 0.05 | 0.0 | 0/1 | 0 | failed |
| fixed | install_five_minute | 0.0 | 0.0 | 0/5 | 0 | failed |
| adaptive | install_five_minute | 0.05 | 0.0 | 0/7 | 2 | failed |
| single | docs_boundary_claims | 0.05 | 0.0 | 0/1 | 0 | failed |
| fixed | docs_boundary_claims | 0.0 | 0.0 | 0/5 | 0 | failed |
| adaptive | docs_boundary_claims | 0.05 | 0.0 | 0/7 | 2 | failed |
| single | tests_dynamic_workflow | 0.05 | 0.0 | 0/1 | 0 | failed |
| fixed | tests_dynamic_workflow | 0.0 | 0.0 | 0/5 | 0 | failed |
| adaptive | tests_dynamic_workflow | 0.1 | 0.0 | 0/7 | 2 | failed |
| single | evidence_redaction | 0.05 | 0.0 | 0/1 | 0 | failed |
| fixed | evidence_redaction | 0.0 | 0.0 | 0/5 | 0 | failed |
| adaptive | evidence_redaction | 0.05 | 0.0 | 0/7 | 2 | failed |

## Limitations

- Manual real benchmark evidence; not part of default CI.
- Raw prompts/stdout/stderr remain in .orchestry/ and are not committed.
- This run was intentionally bounded with 60 second worker/planner timeouts; timeout and failure rows are preserved.
- This proves Codex CLI process-swarm behavior, not App-native isolated subagents.
