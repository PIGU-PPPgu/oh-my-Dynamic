# Release Checklist

Use this checklist before tagging or pushing a public release.

Run the gates inside a virtual environment when using macOS system Python; older
system pip builds can fail editable installs because site-packages is not
writable.

## Required Gates

```bash
git status --short
python3 -m pip install -e ".[dev]"
bash -n install_plugin.sh
test -f LICENSE
python3 -m json.tool .agents/plugins/marketplace.json >/dev/null
python3 -m py_compile *.py examples/*.py scripts/*.py $(find src -name '*.py' -print)
python3 test_suite.py
python3 -m pytest tests -q
python3 -m coverage run -m pytest tests -q
python3 -m coverage report --fail-under=80
python3 -m bandit -r . -c pyproject.toml
python3 -m dynamic_workflow --help >/dev/null
python3 -m codex_cli_swarm --help >/dev/null
python3 -m codex_swarm_cli --help >/dev/null
python3 -m doctor --json >/dev/null
PYTHONPATH=src python3 -m oh_my_dynamic.runtime.dynamic_workflow --help >/dev/null
PYTHONPATH=src python3 -m oh_my_dynamic.codex.codex_cli_swarm --help >/dev/null
python3 scripts/record_swarm_evidence.py --help >/dev/null
python3 scripts/record_adaptive_workflow_evidence.py --help >/dev/null
python3 scripts/render_workflow_observability.py --help >/dev/null
python3 scripts/run_quality_eval.py --help >/dev/null
python3 scripts/run_benchmark.py --help >/dev/null
python3 scripts/run_quality_eval.py --sample --output /tmp/ohmy-quality-eval.md
python3 scripts/run_benchmark.py --suite benchmarks/repo_review.json --mode single,fixed,adaptive --output /tmp/ohmy-benchmark-v310.json
python3 examples/real_repo_review.py --dry-run --run-id ci-dry --output-dir /tmp/ohmy-evidence
python3 scripts/record_adaptive_workflow_evidence.py --required-coverage security,tests,docs,replanner-proof --force-missing-coverage replanner-proof --max-rounds 2 --max-agents 12 --max-parallel 4 --dry-run --output-dir /tmp/ohmy-adaptive
python3 examples/research_analysis.py >/tmp/ohmy-research-demo.txt
python3 examples/code_review.py >/tmp/ohmy-code-review-demo.txt
python3 examples/codex_cli_swarm_review.py --help >/dev/null
python3 examples/real_repo_review.py --help >/dev/null
! grep -R "/Users/" docs/evidence
tmpdir="$(mktemp -d)" && python3 -m pip install . --target "$tmpdir" && (cd /tmp && PYTHONPATH="$tmpdir" python3 -c "from oh_my_dynamic.runtime.dynamic_workflow import DynamicWorkflowRuntime; from oh_my_dynamic.codex.codex_cli_swarm import CodexCliSwarmRuntime; from oh_my_dynamic.broker.agent_broker import AgentBroker")
```

## Optional Stress Gates

```bash
python3 -m doctor --json --strict-real-codex >/tmp/ohmy-strict-doctor.json
python3 test_suite.py --stress
python3 scripts/record_adaptive_workflow_evidence.py --dry-run --run-id adaptive-release-demo --required-coverage security,tests,docs --force-missing-coverage docs --output-dir /tmp/ohmy-evidence
python3 examples/codex_cli_swarm_review.py --agents 20 --max-parallel 5 --total-timeout-s 3600
python3 examples/real_repo_review.py --agents 5 --max-parallel 3
python3 scripts/record_swarm_evidence.py --agents 20 --max-parallel 5
python3 scripts/record_swarm_evidence.py --agents 50 --max-parallel 10
python3 scripts/record_swarm_evidence.py --agents 100 --max-parallel 20
python3 scripts/run_quality_eval.py --sample --output docs/evidence/sample_quality_eval.md
python3 scripts/run_benchmark.py --suite benchmarks/repo_review.json --mode single,fixed,adaptive --output docs/evidence/benchmark_v310_dry.json
python3 scripts/run_benchmark.py --real --suite benchmarks/repo_review.json --mode single,fixed,adaptive --fixtures security_command_surface,install_five_minute,tests_dynamic_workflow,evidence_redaction,docs_boundary_claims --output docs/evidence/benchmark_v310.json
```

## Version And Tag

1. Update `pyproject.toml`.
2. Add a matching `CHANGELOG.md` entry.
3. Commit all release changes.
4. Tag the exact commit:

```bash
git tag vX.Y.Z
git push origin main --tags
```

5. Create or update the GitHub Release and mark the newest stable tag as Latest:

```bash
gh release create vX.Y.Z --latest --title "vX.Y.Z - Release Title" --notes-file /tmp/ohmy-release.md
gh release view vX.Y.Z
```

## Codex App Install Check

```bash
bash install_plugin.sh
python3 -m json.tool ~/.agents/plugins/marketplace.json >/dev/null
bash install_plugin.sh --uninstall
```

Restart Codex App or open a new thread before validating installed skills.
