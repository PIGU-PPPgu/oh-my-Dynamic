## Summary

Describe the behavior or documentation change.

## Boundary

- [ ] Runtime / worker behavior changed
- [ ] Security boundary changed
- [ ] Docs/examples only
- [ ] Evidence or benchmark files changed

## Validation

Paste the commands you ran:

```bash
python test_suite.py
python -m pytest tests -q
python -m coverage run -m pytest tests -q
python -m coverage report --fail-under=80
python -m bandit -r . -c pyproject.toml
python -m doctor --json
```

## Evidence

Link compact evidence paths, if relevant. Do not attach raw `.orchestry/` traces, prompts, stdout, or stderr.

## Notes

Mention any known limits, follow-up work, or release checklist items.
