# Contributing to Alteryx Git Companion

Thank you for your interest in contributing. This document describes how to set up
a development environment, run tests, and submit changes.

## Prerequisites

- Python 3.11 or 3.12
- [uv](https://docs.astral.sh/uv/) 0.5+ (Python package manager)
- Node.js 24 and npm (for the React frontend)
- Git

## Setting up a local development environment

```bash
# Clone the repository
git clone https://github.com/Laxmi884/alteryx-git-companion.git
cd alteryx-git-companion

# Install Python dependencies (including dev extras)
uv sync --group dev

# Build the React frontend
cd app/frontend
npm ci --legacy-peer-deps
npm run build
cd ../..

# Run the application
uv run python -m app.main
```

The desktop app opens a browser window pointing at `http://localhost:7433`.

## Running the test suite

```bash
# Run all tests
uv run pytest tests/ -v

# Run a specific test file
uv run pytest tests/test_git_ops.py -v
```

All tests must pass before submitting a pull request.

## Running linting and type checks

```bash
# Lint (checks style and logic errors)
uv run ruff check .

# Format check (does not modify files)
uv run ruff format --check .

# Type check
uv run mypy src/
```

CI enforces all three; fix any errors before pushing.

## Code style

- **Formatting and linting:** [ruff](https://docs.astral.sh/ruff/) — 88-character line limit, double quotes, Python 3.11 target.
- **Type annotations:** All public functions in `src/` must be fully annotated. mypy strict mode is enforced.
- **Tests:** pytest. Place new tests in `tests/`. Aim for unit tests that do not require a real git repo or running server.

## About Alteryx file types

The project targets Alteryx Designer workflow files. The following extensions are
treated as Alteryx assets:

| Extension | Type |
|-----------|------|
| `.yxmd` | Workflow (most common) |
| `.yxwz` | Analytic App |
| `.yxmc` | Macro |
| `.yxzp` | Packaged Workflow |
| `.yxapp` | Analytic App (legacy) |

When writing parsers or diff logic, ensure all five extensions are handled consistently.

## Pull request guidelines

1. Branch from `main`: `git checkout -b my-feature-branch`
2. Keep PRs focused — one logical change per PR makes review faster.
3. All tests must pass: `uv run pytest tests/ -v`
4. Ruff and mypy must pass (CI will reject otherwise).
5. Write a clear description in the PR body: what changed and why.
6. For bug fixes, include a regression test that would have caught the bug.

## Reporting bugs

Use the [GitHub issue tracker](https://github.com/Laxmi884/alteryx-git-companion/issues)
and fill in the bug report template.

## Questions

Open a [GitHub Discussion](https://github.com/Laxmi884/alteryx-git-companion/discussions)
for general questions.
