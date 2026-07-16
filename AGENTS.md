# AGENTS.md

## Toolchain

- **Package manager**: `uv` (not pip). Use `uv sync` to install, `uv add <pkg>` to add deps.
- **Task runner**: `just`. See `justfile` for common commands (`just setup`, `just install`, `just run <cmd>`).
- **Lint+format**: `ruff check .` and `ruff format .` (run both). Config: `ruff.toml`.
- **Pre-commit**: hooks include ruff (lint+format), mypy (`--disallow-untyped-defs`), nbstripout (notebooks), gitleaks, sqlfluff, nbqa, DVC. Install with `pre-commit install`.
- **SQL**: SQLFluff with Snowflake dialect + dbt templater. Config: `sql/.sqlfluff`.

## Commands

```sh
just setup                          # uv venv + sync + pre-commit install
just run pytest                     # run tests via venv
just run ruff check .               # lint
just run ruff format .              # format
just run mypy src/                  # typecheck
```

## Testing

- `pytest` (config in `pyproject.toml`): test paths `tests/` and `integration/`.
- Fixtures in `conftest.py` as needed. Parametrize with `@pytest.mark.parametrize`.

## Code style

- Ruff: **ALL rules enabled** (see `ruff.toml` `lint.select`). Line length: 120.
- Docstrings: **Google style** (`ruff.toml`: `lint.pydocstyle.convention = "google"`).
- Type hints required (mypy `--disallow-untyped-defs`).
- Quotes: double strings (ruff format, like Black).
- Imports: single-line per import, `combine-as-imports`, known-first-party `["nz-companies-office"]`.

## Architecture

- Source: `src/nz_companies_office/`.
- Data dirs (`data/raw/`, `data/processed/`, `data/staging/`, `data/model_features/`) are git-ignored inside (track only `.gitignore`). Use DVC to version data files.
- `pyproject.toml` defines a CLI entrypoint: `nz-companies-office = "nz-companies-office.main:run"` (module not yet created).

## Git / workflow

- Commits follow [Conventional Commits](https://www.conventionalcommits.org/).
- Branch from `master` as `feature/your-feature-name`.
