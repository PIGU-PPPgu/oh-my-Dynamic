# oh-my-Dynamic Improvement Measurement

## English

Run id: `improvement_v311`
Benchmark: `repo_review_productization_v2`
Type: controlled deterministic scoring, not a live Codex CLI run.
Summary: Controlled same-fixture measurement: adaptive improves average quality score by +0.386 over single, evidence completeness by +0.329, and reduces missing benchmark requirements by 100%.

## Mode Summary

| Mode | Fixtures | Pass Rate | Avg Quality | Evidence Completeness | Missing Requirements | Agents | Replanners |
|------|----------|-----------|-------------|-----------------------|----------------------|--------|------------|
| single | 10 | 0.0 | 0.614 | 0.671 | 70 | 10 | 0 |
| fixed | 10 | 1.0 | 0.9 | 0.9 | 18 | 50 | 0 |
| adaptive | 10 | 1.0 | 1.0 | 1.0 | 0 | 70 | 20 |

## Lift

| Comparison | Quality Lift | Relative Quality Lift | Pass Rate Lift | Evidence Lift | Missing Requirement Reduction |
|------------|--------------|-----------------------|----------------|---------------|-------------------------------|
| fixed_vs_single | 0.286 | 46.6% | 1.0 | 0.229 | 52 (74.3%) |
| adaptive_vs_single | 0.386 | 62.9% | 1.0 | 0.329 | 70 (100.0%) |
| adaptive_vs_fixed | 0.1 | n/a | 0.0 | 0.1 | 18 (100.0%) |

## Interpretation

- Measures: Deterministic requirement coverage and benchmark scoring lift when moving from one reviewer to fixed lanes to adaptive replanner follow-up.
- Does not measure: It does not prove live model answer quality or Codex App-native isolated subagents. Pair with real Codex CLI evidence for runtime proof.

## 中文

运行 ID：`improvement_v311`
测评集：`repo_review_productization_v2`
类型：受控确定性评分，不是真实 Codex CLI 运行。
摘要：受控同题测评：adaptive 相比 single 的平均质量分提升 +0.386，证据完整度提升 +0.329，缺失测评要求减少 100%。

## 模式汇总

| 模式 | Fixture 数 | 通过率 | 平均质量分 | 证据完整度 | 缺失要求数 | 完成 Agent | Replanner 数 |
|------|------------|--------|------------|------------|------------|------------|--------------|
| single | 10 | 0.0 | 0.614 | 0.671 | 70 | 10 | 0 |
| fixed | 10 | 1.0 | 0.9 | 0.9 | 18 | 50 | 0 |
| adaptive | 10 | 1.0 | 1.0 | 1.0 | 0 | 70 | 20 |

## 提升幅度

| 对比 | 质量分提升 | 相对质量提升 | 通过率提升 | 证据完整度提升 | 缺失要求减少 |
|------|------------|--------------|------------|----------------|--------------|
| fixed_vs_single | 0.286 | 46.6% | 1.0 | 0.229 | 52 (74.3%) |
| adaptive_vs_single | 0.386 | 62.9% | 1.0 | 0.329 | 70 (100.0%) |
| adaptive_vs_fixed | 0.1 | n/a | 0.0 | 0.1 | 18 (100.0%) |

## 解读

- 衡量内容：衡量从单个 reviewer 到固定 lane swarm，再到 adaptive replanner follow-up 时，需求覆盖率和 benchmark 评分的确定性提升。
- 不衡量内容：它不证明真实模型回答质量，也不证明 Codex App-native isolated subagents；runtime claim 仍需配合真实 Codex CLI evidence。
