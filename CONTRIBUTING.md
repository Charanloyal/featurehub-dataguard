# Contributing Guidelines

Thank you for your interest in contributing to **FeatureHub & DataGuard**!

## Code Quality Standards

1. **Python Formatting**: Format code using `ruff check` and ensure type hints are added where relevant.
2. **Data Contracts**: Any modification to `dataguard/contracts/` must undergo contract validation via `make test` or `pytest dataguard/tests/test_contracts.py`.
3. **Point-In-Time Leakage**: Any change to `featurehub/point_in_time/` must maintain zero data leakage. Verify with `pytest featurehub/tests/test_pit.py`.
4. **Reproducible Benchmarks**: Do not edit `results.json` directly. All benchmark output files are updated automatically by `make benchmark`.

## Pull Request Lifecycle

- Ensure all existing unit and integration tests pass (`make test`).
- CI will validate contracts and block breaking schema edits unless accompanied by a version migration strategy.
