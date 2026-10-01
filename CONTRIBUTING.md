# Contributing to ClaimLens

Contributions are welcome. Never submit real CVs, candidate PII, salts, secrets, or derived candidate datasets. Tests and bug reports must use synthetic data only.

Before opening a pull request, run:

```bash
pip install -e ".[dev]"
ruff check src tests
pytest -q
```

Network-capable verification providers must be opt-in, declare the exact outbound fields and purpose before execution, and respect the Privacy Review boundary.
