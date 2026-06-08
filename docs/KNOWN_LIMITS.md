# Known Limits

These limits are intentional and should be repeated in release notes, reviews, and benchmark claims.

## Runtime Boundary

- Codex supports native parallel coding-agent workflows.
- oh-my-Dynamic does not claim to implement the Codex App native runtime itself.
- Verified large-scale execution for this project is Codex CLI process swarm.
- If public native subagent APIs become available, oh-my-Dynamic should use them as the execution backend.
- Local Python runtime cannot call Codex App internal LLM APIs unless Codex App exposes an explicit bridge.

## Benchmarks

- Real benchmarks are slow. Adaptive runs are slower because they include planner, workers, replanner, follow-up workers, and reducer.
- Controlled improvement measurement is not live model quality proof. It measures deterministic rubric coverage on fixed fixtures.
- Real Codex CLI evidence proves process-swarm behavior and evidence capture, not that this project owns Codex App-native execution.

## Evidence And Privacy

- Raw `.orchestry/` traces, prompts, stdout, and stderr are not committed.
- Public evidence should be compact, sanitized JSON/Markdown/dashboard records.
- Evidence can preserve failures and timeouts; failure-preserving evidence is preferred over hiding incomplete rows.

## Write Mode

- Default execution is read-only.
- Worktree patch mode must be explicitly enabled.
- Agent worktrees are not auto-merged. Patches/diffs are evidence for review, not automatic changes to `main`.

## Adoption Notes

- Real Codex CLI runs require local Codex CLI installation and login.
- Plugin installation uses symlinks into `~/.agents`; moving the clone requires rerunning `install_plugin.sh`.
- The bash/symlink installer is intended for macOS, Linux, and WSL. Native Windows is not verified.
- External provider API keys are only needed for local provider-backed Python runtime paths, not ordinary Codex App skill usage or Codex CLI login-backed swarm usage.
