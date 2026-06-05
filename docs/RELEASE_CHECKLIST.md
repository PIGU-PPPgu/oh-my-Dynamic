# Release Checklist

Use this checklist before tagging or pushing a public release.

## Required Gates

```bash
git status --short
python3 -m pip install -e ".[dev]"
bash -n install_plugin.sh
python3 -m json.tool .agents/plugins/marketplace.json >/dev/null
python3 -m py_compile *.py examples/*.py scripts/*.py
python3 test_suite.py
python3 -m coverage run test_suite.py
python3 -m coverage report --fail-under=70
python3 -m dynamic_workflow --help >/dev/null
python3 -m codex_cli_swarm --help >/dev/null
python3 -m codex_swarm_cli --help >/dev/null
python3 scripts/record_swarm_evidence.py --help >/dev/null
python3 scripts/render_workflow_observability.py --help >/dev/null
python3 examples/codex_cli_swarm_review.py --help >/dev/null
python3 examples/real_repo_review.py --help >/dev/null
```

## Optional Stress Gates

```bash
python3 test_suite.py --stress
python3 examples/codex_cli_swarm_review.py --agents 20 --max-parallel 5 --total-timeout-s 3600
python3 examples/real_repo_review.py --agents 5 --max-parallel 3
python3 scripts/record_swarm_evidence.py --agents 20 --max-parallel 5
python3 scripts/record_swarm_evidence.py --agents 50 --max-parallel 10
python3 scripts/record_swarm_evidence.py --agents 100 --max-parallel 20
```

## Version And Tag

1. Update `pyproject.toml`.
2. Add a matching `CHANGELOG.md` entry.
3. Commit all release changes.
4. Tag the exact commit:

```bash
git tag v1.9.0
git push origin main --tags
```

## Codex App Install Check

```bash
bash install_plugin.sh
python3 -m json.tool ~/.agents/plugins/marketplace.json >/dev/null
```

Restart Codex App or open a new thread before validating installed skills.
