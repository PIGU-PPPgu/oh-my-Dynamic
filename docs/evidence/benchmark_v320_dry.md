# oh-my-Dynamic Benchmark: repo_review_productization_v2

Run id: `benchmark_v320_95eb8792`
Dry run: `true`
Compact JSON: `benchmark_v320_dry.json`

## Stability Profile

| Field | Value |
|-------|-------|
| version | `v3.2` |
| sandbox | `read-only` |
| timeout_s | `1800` |
| planner_timeout_s | `180` |
| total_timeout_s | `None` |
| max_parallel | `5` |
| prompt_profile | `compact_scoreable` |
| output_redaction | `sanitize_payload` |
| worker_env | `allowlist` |

## Mode Summary

| Mode | Fixtures | Passed | Failed | Avg Score | Evidence | Agents Completed | Agents Failed | Replanners | Duration |
|------|----------|--------|--------|-----------|----------|------------------|---------------|------------|----------|
| single | 10 | 10 | 0 | 1.0 | 1.0 | 10 | 0 | 0 | 0.0s |
| fixed | 12 | 12 | 0 | 1.0 | 1.0 | 60 | 0 | 0 | 0.0s |
| adaptive | 12 | 12 | 0 | 1.0 | 1.0 | 84 | 0 | 24 | 0.0s |

## Fixture Results

| Mode | Fixture | Score | Evidence | Agents | Replanners | State |
|------|---------|-------|----------|--------|------------|-------|
| single | security_command_surface | 1.0 | 1.0 | 1/1 | 0 | completed |
| fixed | security_command_surface | 1.0 | 1.0 | 5/5 | 0 | completed |
| adaptive | security_command_surface | 1.0 | 1.0 | 7/7 | 2 | completed |
| single | security_broker_poisoning | 1.0 | 1.0 | 1/1 | 0 | completed |
| fixed | security_broker_poisoning | 1.0 | 1.0 | 5/5 | 0 | completed |
| adaptive | security_broker_poisoning | 1.0 | 1.0 | 7/7 | 2 | completed |
| single | install_five_minute | 1.0 | 1.0 | 1/1 | 0 | completed |
| fixed | install_five_minute | 1.0 | 1.0 | 5/5 | 0 | completed |
| adaptive | install_five_minute | 1.0 | 1.0 | 7/7 | 2 | completed |
| single | docs_boundary_claims | 1.0 | 1.0 | 1/1 | 0 | completed |
| fixed | docs_boundary_claims | 1.0 | 1.0 | 5/5 | 0 | completed |
| adaptive | docs_boundary_claims | 1.0 | 1.0 | 7/7 | 2 | completed |
| single | tests_dynamic_workflow | 1.0 | 1.0 | 1/1 | 0 | completed |
| fixed | tests_dynamic_workflow | 1.0 | 1.0 | 5/5 | 0 | completed |
| adaptive | tests_dynamic_workflow | 1.0 | 1.0 | 7/7 | 2 | completed |
| single | tests_failure_modes | 1.0 | 1.0 | 1/1 | 0 | completed |
| fixed | tests_failure_modes | 1.0 | 1.0 | 5/5 | 0 | completed |
| adaptive | tests_failure_modes | 1.0 | 1.0 | 7/7 | 2 | completed |
| single | evidence_redaction | 1.0 | 1.0 | 1/1 | 0 | completed |
| fixed | evidence_redaction | 1.0 | 1.0 | 5/5 | 0 | completed |
| adaptive | evidence_redaction | 1.0 | 1.0 | 7/7 | 2 | completed |
| fixed | dashboard_observability | 1.0 | 1.0 | 5/5 | 0 | completed |
| adaptive | dashboard_observability | 1.0 | 1.0 | 7/7 | 2 | completed |
| single | release_gates | 1.0 | 1.0 | 1/1 | 0 | completed |
| fixed | release_gates | 1.0 | 1.0 | 5/5 | 0 | completed |
| adaptive | release_gates | 1.0 | 1.0 | 7/7 | 2 | completed |
| single | benchmark_claims | 1.0 | 1.0 | 1/1 | 0 | completed |
| fixed | benchmark_claims | 1.0 | 1.0 | 5/5 | 0 | completed |
| adaptive | benchmark_claims | 1.0 | 1.0 | 7/7 | 2 | completed |
| fixed | worktree_write_isolation | 1.0 | 1.0 | 5/5 | 0 | completed |
| adaptive | worktree_write_isolation | 1.0 | 1.0 | 7/7 | 2 | completed |
| single | llm_provider_docs | 1.0 | 1.0 | 1/1 | 0 | completed |
| fixed | llm_provider_docs | 1.0 | 1.0 | 5/5 | 0 | completed |
| adaptive | llm_provider_docs | 1.0 | 1.0 | 7/7 | 2 | completed |

## Limitations

- Dry-run benchmark validates scoring shape only; it does not launch Codex CLI.
- Use --real for release evidence backed by Codex CLI workers.
