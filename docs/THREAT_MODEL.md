# oh-my-Dynamic Threat Model

This project runs agentic workflows over local repositories. The safe default is
read-only Codex CLI process swarm. Write-capable worktree mode and HTTP gateway
exposure must be explicitly enabled.

## Trust Boundaries

| Boundary | Trusted? | Main risks | Controls |
|----------|----------|------------|----------|
| User goal / prompt | No | Prompt injection, unsafe write requests | Read-only default, explicit write/worktree mode, release checklist review |
| Repository content | No | Malicious instructions in files, poisoned examples | Workers are prompted to treat repo content as data; evidence remains compact |
| Codex CLI worker | Partially | Tool misuse, raw stderr/stdout leakage, env exposure | Read-only sandbox by default, argv subprocesses, raw output kept under `.orchestry/` |
| Agent envelope | No | Malformed JSON, fake artifact references, fake approvals | Envelope validation, registered agent checks, artifact ref checks |
| Broker artifact | No | Artifact poisoning, oversized content, replay/confusion | Content-type allowlist, size caps, thread/task IDs, append-only logs |
| Gateway client | No | Unauthorized task/inbox access | Loopback default, token auth for non-loopback, per-agent actor tokens |
| Dashboard/evidence | Public | Local path leaks, credential-looking output | Evidence sanitizer, sensitive scan, no raw prompts/stdout/stderr committed |

## Threats And Mitigations

- Prompt injection: keep workers read-only by default; do not treat repo text,
  issue comments, or artifact bodies as trusted instructions.
- Artifact poisoning: require registered senders and known artifact IDs before
  broker ingestion; reducer must show artifact IDs and terminal state.
- Fake reviewer approval: review responses are broker events, not authority to
  merge or write; no worktree is auto-merged.
- Credential-looking output: compact evidence is sanitized and scanned before
  release; raw worker output stays in `.orchestry/`.
- Path traversal: agent IDs and worktree names must use safe slugs; evidence
  paths are normalized to `$REPO_ROOT` or `.orchestry/...`.
- Oversized artifact: broker policy caps body and artifact sizes.
- Broker replay: task snapshots filter by thread/task; release dashboards must
  show run IDs and source thread IDs.
- Raw stderr leakage: failure artifacts are useful diagnostics but should be
  reviewed before publishing evidence.

## Release Gates

Before publishing release evidence:

```bash
python -m bandit -r . -c pyproject.toml
python -m doctor --json
python scripts/run_benchmark.py --suite benchmarks/repo_review.json --mode single,fixed,adaptive --output /tmp/benchmark_v240.json
! grep -R "/Users/" docs/evidence
```

Manual Codex CLI smoke runs may write raw traces under `.orchestry/`; these are
local-only diagnostics and must not be committed.
