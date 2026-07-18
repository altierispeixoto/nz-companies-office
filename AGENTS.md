# AGENTS.md

## Toolchain

- **Package manager**: `uv` (not pip). Use `uv sync` to install, `uv add <pkg>` to add deps.
- **Task runner**: `just`. See `justfile` for common commands (`just setup`, `just install`, `just run <cmd>`).
- **Lint+format**: `ruff check .` and `ruff format .` (run both). Config: `ruff.toml`.
- **Pre-commit**: hooks include pre-commit-hooks, ruff (lint), ruff-format, and mypy (`--disallow-untyped-defs`). Install with `pre-commit install` (see `.pre-commit-config.yaml`).
- **SQL**: SQLFluff config exists at `sql/.sqlfluff` (Snowflake dialect). It is **not** currently wired into pre-commit; DVC/notebook/Gitleaks hooks are not configured.

## Commands

```sh
just setup                          # uv venv + sync + pre-commit install
just run pytest                     # run tests via venv
just run ruff check .               # lint
just run ruff format .              # format
just run mypy src/                  # typecheck
just geocode                        # reverse geocode Address nodes (add --sample N for quick test)
just geocode --sample 500           # test run on 500 random addresses (no separate command needed)
just prepare-linz                   # transform LINZ shapefile into a cached parquet file
just enrich                         # post-load enrichment (share %)
just entity-resolution              # entity resolution pipeline
just load-db                        # drop + reload Neo4j graph
just fetch <num>                    # fetch company from NZBN API
```

## Testing

- `pytest` (config in `pyproject.toml`): test path `tests/` (`integration/` directory does not currently exist).
- Add `tests/conftest.py` for shared fixtures as needed. Parametrize with `@pytest.mark.parametrize`.
- Ruff `PLR2004` (magic numbers) suppressed with `# noqa: PLR2004` in test files.

## Code style

- Ruff: **ALL rules enabled** (see `ruff.toml` `lint.select`). Line length: 120.
- Docstrings: **Google style** (`ruff.toml`: `lint.pydocstyle.convention = "google"`).
- Type hints required (mypy `--disallow-untyped-defs`).
- Quotes: double strings (ruff format, like Black).
- Imports: single-line per import, `combine-as-imports`, known-first-party `["nz-companies-office"]`.
- **Object Oriented Programming**: use classes with single responsibility, prefer composition over inheritance, encapsulate related data and behaviour.
- **Design patterns**: follow established patterns (Strategy, Factory, Repository, etc.) where appropriate. Keep interfaces clean and documented.
- **Unit tests**: always create or update unit tests for every new function, class, or behaviour change. Tests must be deterministic and isolated (no network/DB calls).
- **Logging**: always use the `logging` module with `logger = logging.getLogger(__name__)` at module level. Use `colorlog` for coloured console output where appropriate.

## Architecture

- Source: `src/nz_companies_office/`.
- CLI entrypoint: `nz-companies-office = "nz_companies_office.cli.main:run"` (in `pyproject.toml`).
- Subcommands: `fetch`, `csv-fetch`, `load-db`, `er`, `enrich`, `prepare-linz`, `geocode`.
- Data dirs (`data/raw/`, `data/processed/`, `data/staging/`, `data/model_features/`) are git-ignored inside (track only `.gitignore`).

## Planning

Always load the **tlc-spec-driven** skill for project planning, feature specification, task breakdown, and implementation. This covers:

- Initializing projects (vision, goals, roadmap)
- Mapping existing codebases (stack, architecture, conventions)
- Specifying features (requirements, design, task breakdown)
- Implementing with verification and atomic commits
- Quick ad-hoc tasks (bug fixes, config changes)
- Tracking decisions, blockers, and deferred ideas across sessions
- Pausing and resuming work

When planning a new feature or task, load the skill with: `skill tlc-spec-driven`

## Git / workflow

- Commits follow [Conventional Commits](https://www.conventionalcommits.org/).
- The default branch is `main` (there is no `master`). Branch as `feat/your-feature-name` or `fix/your-fix-name` (existing branches use these prefixes).
