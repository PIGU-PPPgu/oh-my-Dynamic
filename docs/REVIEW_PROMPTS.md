# External Review Prompts

Use these prompts with GPT Pro, GLM, Claude Code, Codex, or another reviewer. Commit only compact summaries, not raw prompts/stdout/stderr.

## Adoption Review

```text
Review oh-my-Dynamic v3.3 from an external adopter perspective.

Focus on:
- installation failure points
- README or Quickstart confusion
- Codex App-native vs Codex CLI process-swarm boundary
- evidence credibility
- benchmark interpretation
- security/adoption blockers
- examples that may not run as documented

Output:
1. Top risks
2. Missing adoption blockers
3. Docs confusion
4. Evidence or benchmark concerns
5. Recommended next release
```

## Security Boundary Review

```text
Review oh-my-Dynamic v3.3 security boundaries.

Focus on:
- worker environment handling
- codex exec args and sandbox assumptions
- broker artifact poisoning
- evidence redaction
- raw .orchestry retention
- gateway/auth boundaries
- worktree patch mode and no-auto-merge behavior

Output:
1. High severity findings
2. Medium severity findings
3. False-positive or already-mitigated risks
4. Concrete tests or docs to add
```

## Benchmark Review

```text
Review oh-my-Dynamic v3.3 benchmark claims.

Focus on:
- controlled improvement measurement vs real Codex CLI evidence
- whether single/fixed/adaptive comparisons are fair
- timeout/failure handling
- evidence completeness scoring
- what claims are supported and what claims are not supported

Output:
1. Supported claims
2. Unsupported or overstated claims
3. Missing measurements
4. Recommended benchmark changes
```
