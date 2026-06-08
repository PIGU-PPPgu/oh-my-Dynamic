# oh-my-Dynamic Docs

This folder holds the long-form material that used to crowd the project README. The short entrypoints are [README.md](../README.md) and [README.zh-CN.md](../README.zh-CN.md); these docs carry architecture, release, evidence, and migration detail.

## Start Here

| Need | Document |
|------|----------|
| Five-minute setup and first run | [QUICKSTART.md](QUICKSTART.md) / [QUICKSTART.zh-CN.md](QUICKSTART.zh-CN.md) |
| Fresh-clone adoption validation | [ADOPTION_VALIDATION.md](ADOPTION_VALIDATION.md) / [ADOPTION_VALIDATION.zh-CN.md](ADOPTION_VALIDATION.zh-CN.md) |
| Troubleshooting, strict doctor, and uninstall | [TROUBLESHOOTING.md](TROUBLESHOOTING.md) / [TROUBLESHOOTING.zh-CN.md](TROUBLESHOOTING.zh-CN.md) |
| Official-facing brief | [OFFICIAL_BRIEF.md](OFFICIAL_BRIEF.md) / [OFFICIAL_BRIEF.zh-CN.md](OFFICIAL_BRIEF.zh-CN.md) |
| Codex native agents vs oh-my-Dynamic | [CODEX_NATIVE_VS_OH_MY_DYNAMIC.md](CODEX_NATIVE_VS_OH_MY_DYNAMIC.md) / [CODEX_NATIVE_VS_OH_MY_DYNAMIC.zh-CN.md](CODEX_NATIVE_VS_OH_MY_DYNAMIC.zh-CN.md) |
| Five-minute demo script | [DEMO_SCRIPT.md](DEMO_SCRIPT.md) / [DEMO_SCRIPT.zh-CN.md](DEMO_SCRIPT.zh-CN.md) |
| Remotion video showcase | [VIDEO_SHOWCASE.md](VIDEO_SHOWCASE.md) / [VIDEO_SHOWCASE.zh-CN.md](VIDEO_SHOWCASE.zh-CN.md) |
| Demo validation and measured adoption scenarios | [DEMOS.md](DEMOS.md) / [DEMOS.zh-CN.md](DEMOS.zh-CN.md) |
| Outreach copy pack | [OUTREACH.md](OUTREACH.md) / [OUTREACH.zh-CN.md](OUTREACH.zh-CN.md) |
| Current product limits and claim boundaries | [KNOWN_LIMITS.md](KNOWN_LIMITS.md) / [KNOWN_LIMITS.zh-CN.md](KNOWN_LIMITS.zh-CN.md) |
| Evidence format, redaction rules, and reproduction notes | [evidence/README.md](evidence/README.md) |
| Codex CLI fixed swarm scale notes | [CODEX_CLI_SWARM_SMOKE.md](CODEX_CLI_SWARM_SMOKE.md) |
| Native dynamic workflow proposal and App runtime boundary | [CODEX_NATIVE_DYNAMIC_WORKFLOWS.md](CODEX_NATIVE_DYNAMIC_WORKFLOWS.md) |
| Security assumptions and mitigations | [THREAT_MODEL.md](THREAT_MODEL.md) |
| Release gates and publishing checklist | [RELEASE_CHECKLIST.md](RELEASE_CHECKLIST.md) |
| v3 package import migration | [V3_MIGRATION_GUIDE.md](V3_MIGRATION_GUIDE.md) |
| External reviewer prompt pack | [REVIEW_PROMPTS.md](REVIEW_PROMPTS.md) / [REVIEW_PROMPTS.zh-CN.md](REVIEW_PROMPTS.zh-CN.md) |

## Evidence Records

Committed evidence is compact and sanitized. Raw `.orchestry/` traces, prompts, stdout, and stderr stay local.

| Evidence | Summary |
|----------|---------|
| [evidence/benchmark_v320_real_smoke.md](evidence/benchmark_v320_real_smoke.md) | v3.2 real stability smoke with compact prompt profile and adaptive replanner completion |
| [evidence/benchmark_v310.md](evidence/benchmark_v310.md) | Bounded real Codex CLI benchmark across single, fixed, and adaptive modes |
| [evidence/improvement_v311.md](evidence/improvement_v311.md) | Bilingual controlled same-fixture lift measurement for single vs fixed vs adaptive |
| [evidence/demo_validation_v360.md](evidence/demo_validation_v360.md) | Demo validation for frontend build, harness engineering, productization, and security/trust scenarios |
| [evidence/benchmark_v310_replanner_sample.md](evidence/benchmark_v310_replanner_sample.md) | Real adaptive run with replanner-generated follow-up agents |
| [evidence/swarm_100_agents_codex_cli_run_98b78a645c.md](evidence/swarm_100_agents_codex_cli_run_98b78a645c.md) | Fixed 100-agent Codex CLI swarm record |

## Current Product Boundary

Codex itself supports native parallel coding-agent workflows. oh-my-Dynamic's stable product path is a reproducible workflow/evidence harness around Codex CLI/App workflows: planner/replanner orchestration, broker evidence, compact evaluation artifacts, and optional static dashboards.

The oh-my-Dynamic App-native bridge remains experimental because this project does not currently own Codex App's native subagent runtime, sandbox, scheduler, or tool-permission contracts.
