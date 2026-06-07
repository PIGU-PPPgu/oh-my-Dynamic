# Demo Validation v3.6 / Demo 验证 v3.6

Run id: `demo_validation_v360`
Dry run: `true`
Compact JSON: `demo_validation_v360.json`

## Claim Boundary / 声明边界

This deterministic demo measures workflow coverage, evidence completeness, parallel review throughput, and gap-driven replanning. It does not prove live model quality.

这个确定性 demo 衡量的是任务覆盖、证据完整度、并行审查吞吐和基于缺口的重规划；它不证明真实模型质量提升。

## Mode Summary

| Mode | Scenarios | Avg Quality | Evidence | Speedup | Missing Requirements | Replanner Agents |
|------|-----------|-------------|----------|---------|----------------------|------------------|
| single | 4 | 0.56 | 0.48 | 1.0x | 20 | 0 |
| fixed | 4 | 0.74 | 0.78 | 3.48x | 8 | 0 |
| adaptive | 4 | 0.88 | 0.94 | 3.5x | 0 | 8 |

## Lift vs Single

| Comparison | Quality Lift | Evidence Lift | Missing Requirement Reduction | Speedup Lift |
|------------|--------------|---------------|-------------------------------|--------------|
| fixed_vs_single | 0.18 | 0.3 | 60.0% | 2.48x |
| adaptive_vs_single | 0.32 | 0.46 | 100.0% | 2.5x |

## Scenario Results

| Scenario | Mode | Quality | Evidence | Speedup | Missing | Replanners | Interpretation |
|----------|------|---------|----------|---------|---------|------------|----------------|
| frontend_build | single | 0.56 | 0.48 | 1.0x | 5 | 0 | Single baseline covers the first-pass path for frontend_build, but leaves 5 requirement(s) without explicit evidence. |
| frontend_build | fixed | 0.74 | 0.78 | 3.48x | 2 | 0 | Fixed swarm increases specialist coverage for frontend_build, but cannot create follow-up agents for tests, docs. |
| frontend_build | adaptive | 0.88 | 0.94 | 3.5x | 0 | 2 | Adaptive workflow closes the planned coverage lanes for frontend_build by adding replanner-generated follow-up agents. |
| harness_engineering | single | 0.56 | 0.48 | 1.0x | 5 | 0 | Single baseline covers the first-pass path for harness_engineering, but leaves 5 requirement(s) without explicit evidence. |
| harness_engineering | fixed | 0.74 | 0.78 | 3.48x | 2 | 0 | Fixed swarm increases specialist coverage for harness_engineering, but cannot create follow-up agents for evidence-schema, failure-preservation. |
| harness_engineering | adaptive | 0.88 | 0.94 | 3.5x | 0 | 2 | Adaptive workflow closes the planned coverage lanes for harness_engineering by adding replanner-generated follow-up agents. |
| repo_productization | single | 0.56 | 0.48 | 1.0x | 5 | 0 | Single baseline covers the first-pass path for repo_productization, but leaves 5 requirement(s) without explicit evidence. |
| repo_productization | fixed | 0.74 | 0.78 | 3.48x | 2 | 0 | Fixed swarm increases specialist coverage for repo_productization, but cannot create follow-up agents for release-checklist, evidence. |
| repo_productization | adaptive | 0.88 | 0.94 | 3.5x | 0 | 2 | Adaptive workflow closes the planned coverage lanes for repo_productization by adding replanner-generated follow-up agents. |
| security_trust | single | 0.56 | 0.48 | 1.0x | 5 | 0 | Single baseline covers the first-pass path for security_trust, but leaves 5 requirement(s) without explicit evidence. |
| security_trust | fixed | 0.74 | 0.78 | 3.48x | 2 | 0 | Fixed swarm increases specialist coverage for security_trust, but cannot create follow-up agents for threat-model, bandit. |
| security_trust | adaptive | 0.88 | 0.94 | 3.5x | 0 | 2 | Adaptive workflow closes the planned coverage lanes for security_trust by adding replanner-generated follow-up agents. |

## Scenarios / 场景

### Frontend Build Demo / 前端建设 Demo

- Goal: Add a dashboard/report page to a small React/Vite app and validate it before handoff.
- Requirements: layout, state, data-contract, accessibility, responsive, visual-regression, tests, docs
- Coverage lanes: ui-layout, state-data, a11y, responsive-review, visual-review, test-authoring, docs-handoff, replanner-gap-fix
- Guardrail: This measures workflow coverage for frontend construction, not visual taste or model creativity.

### Harness Engineering Demo / Harness 工程 Demo

- Goal: Design an evaluation harness with fixtures, scoring, redaction, CI gates, and evidence reports.
- Requirements: fixtures, scoring-rubric, redaction, ci-gate, dry-run, real-run-boundary, evidence-schema, failure-preservation
- Coverage lanes: fixture-designer, rubric-reviewer, redaction-reviewer, ci-integrator, evidence-writer, failure-triage, replanner-gap-fix
- Guardrail: This measures harness completeness and reproducibility, not benchmark generality.

### Repo Productization Demo / 项目产品化 Demo

- Goal: Turn a research prototype into an externally adoptable repository.
- Requirements: install, doctor, quickstart, known-limits, tests, coverage, release-checklist, evidence
- Coverage lanes: install-review, doctor-review, docs-review, test-review, release-review, evidence-review, replanner-gap-fix
- Guardrail: This measures adoption readiness, not package popularity.

### Security / Trust Demo / 安全与可信 Demo

- Goal: Review command surface, broker artifacts, gateway auth, evidence redaction, and raw-output boundaries.
- Requirements: command-surface, gateway-auth, artifact-poisoning, secret-redaction, path-redaction, raw-output-boundary, threat-model, bandit
- Coverage lanes: command-review, gateway-review, artifact-review, redaction-review, threat-model-review, bandit-review, replanner-gap-fix
- Guardrail: This measures review coverage and evidence discipline, not a formal security audit.

## Limitations / 限制

- Deterministic dry-run evidence; no Codex CLI workers are launched.
- Numbers are scenario fixtures for external explanation, not a live benchmark.
- Pair this report with real Codex CLI evidence before making runtime claims.
- 这是确定性 dry-run 证据，不启动 Codex CLI workers。
- 数值用于场景化解释，不是真实 benchmark。
- 涉及 runtime claim 时，应同时引用真实 Codex CLI evidence。
