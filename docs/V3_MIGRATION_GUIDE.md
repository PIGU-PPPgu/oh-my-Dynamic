# v3 Migration Guide

v3.0 moved oh-my-Dynamic from root-level modules into the standard
`src/oh_my_dynamic/` package layout. Runtime behavior and user commands did not
change.

## What Still Works

Root-level imports remain compatibility shims for the v3 major line:

```python
from dynamic_workflow import DynamicWorkflowRuntime
from codex_cli_swarm import CodexCliSwarmRuntime, CodexCliAgentSpec
from agent_broker import AgentBroker
```

Module commands also remain available:

```bash
python -m dynamic_workflow --help
python -m codex_cli_swarm --help
python -m doctor --json
```

These shims may be removed in a future v4 cleanup after another release cycle.

## Preferred Imports

New code should import from the package paths:

```python
from oh_my_dynamic.runtime.dynamic_workflow import DynamicWorkflowRuntime
from oh_my_dynamic.codex.codex_cli_swarm import CodexCliSwarmRuntime, CodexCliAgentSpec
from oh_my_dynamic.broker.agent_broker import AgentBroker
from oh_my_dynamic.evals.evidence_sanitizer import sanitize_payload
```

## Console Scripts

Editable and normal installs expose the same entrypoints:

```bash
oh-my-dynamic-dynamic-workflow --help
oh-my-dynamic-codex-swarm --help
oh-my-dynamic-gateway --help
oh-my-dynamic-quality-eval --help
oh-my-dynamic-doctor --json
```

## Package Map

| Area | Package |
|------|---------|
| Dynamic workflow runtime | `oh_my_dynamic.runtime` |
| Codex CLI swarm and Codex App bridge | `oh_my_dynamic.codex` |
| Broker, gateway, reducer | `oh_my_dynamic.broker` |
| Evidence, doctor, observer, evals | `oh_my_dynamic.evals` |
| MCP/A2A-style adapters | `oh_my_dynamic.protocol` |
| Shared primitives and helpers | `oh_my_dynamic.core` |
| Console script wrappers | `oh_my_dynamic.cli` |

## Migration Steps

1. Replace root imports with package imports in application code.
2. Keep CLI commands unchanged unless you prefer console scripts.
3. Run:

```bash
python3 -m pytest tests -q
python3 -m coverage run -m pytest tests -q
python3 -m coverage report --fail-under=80
```

4. If you publish evidence, run `python -m doctor --json` and the evidence
   redaction scan from `docs/RELEASE_CHECKLIST.md`.

The root façade files are intentionally small and should not be used as the
place to add new behavior. Add new runtime behavior under `src/oh_my_dynamic/`
and let the façade re-export it.
