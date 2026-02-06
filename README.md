# python-template
Template repository for Python projects using `uv`.

## Setup

1. Create or update the environment: `uv sync --locked`
2. Activate it (optional): `source .venv/bin/activate`
3. Install git hooks: `uv run pre-commit install`
4. Run tests: `uv run pytest`

`uv sync` installs the project itself into `.venv` by default, so a separate `pip install -e .` step is not needed.

## Daily Commands

- Run package entrypoint: `uv run python -m python_template`
- Run tests: `uv run pytest`
- Lint and auto-fix: `uv run ruff check --fix .`
- Format: `uv run ruff format .`

## Dependency Management

`pyproject.toml` is the source of truth for dependencies.

- Add runtime dependency: `uv add <package>`
- Add dev dependency: `uv add --dev <package>`
- Remove dependency: `uv remove <package>`
- Refresh lockfile after changes: `uv lock`
- Upgrade locked packages: `uv lock --upgrade`

Inspect the resolved dependency graph with `uv tree`.

## Environment Variables

`python-dotenv` is used for loading `.env` values.
Start from [`.env.example`](.env.example) when creating local environment files.
