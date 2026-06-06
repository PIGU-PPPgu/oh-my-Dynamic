# v3.1 Adaptive Replanner Sample

Run id: `benchmark_v310_real_20260607c_adaptive_security_command_surface`

This is compact manual evidence derived from local `.orchestry/` traces. Raw
prompts, stdout, stderr, and full worker outputs are not committed.

| Field | Value |
|-------|-------|
| Fixture | `security_command_surface` |
| Mode | `adaptive` |
| Planner-generated agents | 3 |
| Replanner-generated agents | 2 |
| Agents completed | 3 |
| Agents failed | 2 |
| Terminal state | `partial` |

## Round Timeline

| Round | Source | Agents | Completed | Failed |
|-------|--------|--------|-----------|--------|
| 0 | planner | 3 | 2 | 1 |
| 1 | replanner | 2 | 1 | 1 |

## Replan Triggers

- `missing_coverage`: `benchmark_followup`
- `failed_agents`: `process_lifecycle_reviewer`

## Limitations

- This proves real planner/replanner fan-out and follow-up agent creation, not a fully passing quality benchmark.
- Two agents timed out under the 180 second worker bound.
- The 5-fixture bounded smoke is recorded separately in `benchmark_v310.json`.
