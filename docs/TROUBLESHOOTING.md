# Troubleshooting And Uninstall

## Platform

- Supported first-run platforms: macOS, Linux, WSL.
- Native Windows is not verified. Use WSL for the bash installer and symlink-based Codex App plugin path.

## Doctor

Safe dry-run readiness:

```bash
python -m doctor --json
```

Real Codex CLI worker readiness:

```bash
python -m doctor --json --strict-real-codex
```

`--strict-real-codex` runs a minimal read-only `codex exec` smoke. It may fail when Codex CLI is missing, logged out, blocked by local config, or unable to use the requested sandbox.

## Codex CLI Issues

Check:

```bash
codex --version
python -m doctor --json --strict-real-codex
```

If strict doctor fails, fix Codex CLI login/config before running real swarm commands. Dry-runs do not require Codex CLI.

## Plugin Install And Uninstall

Install only when you want Codex App skills:

```bash
bash install_plugin.sh
```

This creates symlinks under `~/.agents/skills` and `~/.agents/plugins`, and merges an `oh-my-dynamic` entry into `~/.agents/plugins/marketplace.json`.

Uninstall:

```bash
bash install_plugin.sh --uninstall
```

The uninstall path removes only symlinks pointing at the current clone and removes the marketplace entry after backing up the JSON file. It skips non-symlink paths to avoid deleting user content.

## Clean Generated Files

Raw traces and worker outputs:

```bash
rm -rf .orchestry
```

New-user dry-runs should write outside the repo:

```bash
python examples/real_repo_review.py --dry-run --run-id five-minute-demo --output-dir /tmp/ohmy-evidence
```

Only commit compact sanitized evidence intentionally created for a release.

## Common Failures

| Symptom | Likely cause | Fix |
|---------|--------------|-----|
| `doctor` returns `warn` for `codex_cli` | Codex CLI is absent | OK for dry-run; install/login Codex CLI for real workers |
| `--strict-real-codex` fails | CLI login/config/sandbox issue | Run Codex CLI manually, then retry strict doctor |
| `unknown variant ... service_tier` | Codex CLI config uses an unsupported service tier | update local Codex CLI config to a supported value such as `fast` or `flex` |
| installer says target exists and is not symlink | existing user skill/plugin path | back it up manually or use a different profile |
| plugin disappears after moving clone | symlink target moved | rerun `bash install_plugin.sh` |
| dry-run dirties `docs/evidence` | omitted `--output-dir` | use `/tmp/ohmy-evidence` for first-run checks |
