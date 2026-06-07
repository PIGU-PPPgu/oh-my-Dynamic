# oh-my-Dynamic Docs

This folder holds the long-form material that used to crowd the project README. The README is now the product entrypoint; these docs carry architecture, release, evidence, and migration detail.

## Start Here

| Need | Document |
|------|----------|
| Evidence format, redaction rules, and reproduction notes | [evidence/README.md](evidence/README.md) |
| Codex CLI fixed swarm scale notes | [CODEX_CLI_SWARM_SMOKE.md](CODEX_CLI_SWARM_SMOKE.md) |
| Native dynamic workflow proposal and App runtime boundary | [CODEX_NATIVE_DYNAMIC_WORKFLOWS.md](CODEX_NATIVE_DYNAMIC_WORKFLOWS.md) |
| Security assumptions and mitigations | [THREAT_MODEL.md](THREAT_MODEL.md) |
| Release gates and publishing checklist | [RELEASE_CHECKLIST.md](RELEASE_CHECKLIST.md) |
| v3 package import migration | [V3_MIGRATION_GUIDE.md](V3_MIGRATION_GUIDE.md) |

## Evidence Records

Committed evidence is compact and sanitized. Raw `.orchestry/` traces, prompts, stdout, and stderr stay local.

| Evidence | Summary |
|----------|---------|
| [evidence/benchmark_v310.md](evidence/benchmark_v310.md) | Bounded real Codex CLI benchmark across single, fixed, and adaptive modes |
| [evidence/improvement_v311.md](evidence/improvement_v311.md) | Bilingual controlled same-fixture lift measurement for single vs fixed vs adaptive |
| [evidence/benchmark_v310_replanner_sample.md](evidence/benchmark_v310_replanner_sample.md) | Real adaptive run with replanner-generated follow-up agents |
| [evidence/swarm_100_agents_codex_cli_run_98b78a645c.md](evidence/swarm_100_agents_codex_cli_run_98b78a645c.md) | Fixed 100-agent Codex CLI swarm record |

## Current Product Boundary

The stable product path is Codex CLI dynamic workflow: planner/replanner orchestration around `codex exec` workers, broker evidence, compact evaluation artifacts, and optional static dashboards.

Codex App-native isolated subagents remain experimental because they depend on Codex App exposing native subagent runtime, sandbox, scheduler, and tool-permission APIs.
