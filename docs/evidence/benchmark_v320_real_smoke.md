# oh-my-Dynamic Benchmark: repo_review_productization_v2

Run id: `benchmark_v310_0ff513f7`
Dry run: `false`
Compact JSON: `benchmark_v320_real_smoke.json`

## Stability Profile

| Field | Value |
|-------|-------|
| version | `v3.2` |
| sandbox | `read-only` |
| timeout_s | `240` |
| planner_timeout_s | `180` |
| total_timeout_s | `1200` |
| max_parallel | `2` |
| prompt_profile | `compact_scoreable` |
| output_redaction | `sanitize_payload` |
| worker_env | `allowlist` |

## Mode Summary

| Mode | Fixtures | Passed | Failed | Avg Score | Evidence | Agents Completed | Agents Failed | Replanners | Duration |
|------|----------|--------|--------|-----------|----------|------------------|---------------|------------|----------|
| single | 1 | 0 | 1 | 0.537 | 0.396 | 1 | 0 | 0 | 149.09s |
| fixed | 1 | 1 | 0 | 0.838 | 0.688 | 5 | 0 | 0 | 489.92s |
| adaptive | 1 | 1 | 0 | 1.0 | 1.0 | 4 | 0 | 1 | 720.72s |

## Fixture Results

| Mode | Fixture | Score | Evidence | Agents | Replanners | State |
|------|---------|-------|----------|--------|------------|-------|
| single | install_five_minute | 0.537 | 0.396 | 1/1 | 0 | partial |
| fixed | install_five_minute | 0.838 | 0.688 | 5/5 | 0 | completed |
| adaptive | install_five_minute | 1.0 | 1.0 | 4/4 | 1 | completed |

## Limitations

- Manual real benchmark evidence; not part of default CI.
- Raw prompts/stdout/stderr remain in .orchestry/ and are not committed.
- Real runs may be intentionally bounded by timeout-s/planner-timeout-s; timeout and failure rows are preserved.
- This proves Codex CLI process-swarm behavior, not App-native isolated subagents.
