# oh-my-Dynamic Improvement Measurement

Run id: `improvement_v311`
Benchmark: `repo_review_productization_v2`
Type: controlled deterministic scoring, not a live Codex CLI run.

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
