# AGENTS.md

## Toolchain

- **Package manager**: `uv` (not pip). Use `uv sync` to install, `uv add <pkg>` to add deps.
- **Task runner**: `just`. See `justfile` for common commands (`just setup`, `just install`, `just run <cmd>`).
- **Lint+format**: `ruff check .` and `ruff format .` (run both). Config: `ruff.toml`.
- **Pre-commit**: hooks include pre-commit-hooks, ruff (lint), ruff-format, and mypy (`--disallow-untyped-defs`). Install with `pre-commit install` (see `.pre-commit-config.yaml`).
- **SQL**: SQLFluff config exists at `data_ingestion/sql/.sqlfluff` (DuckDB dialect). It is **not** currently wired into pre-commit; notebook/Gitleaks hooks are not configured.
- **Medallion pipeline**: `data/raw/` → `data/bronze/` → `data/silver/` → `data/gold/` → Neo4j, orchestrated by **Dagster** (top-level `data_ingestion/` package — not under `src/`), transformed with **DuckDB** SQL (`data_ingestion/sql/{bronze,silver,gold}/`). See `.specs/features/medallion-architecture/` for spec/design/tasks. All previously-loaded source tables now flow through the pipeline (Increments 1 & 2 complete, see `.specs/project/ROADMAP.md`); the 5 "other entity register" CSVs that were never loaded into the graph remain untouched.

## Commands

```sh
just setup                          # uv venv + sync + pre-commit install
just run pytest                     # run tests via venv
just run ruff check .               # lint
just run ruff format .              # format
just run mypy src/ data_ingestion/ machine_learning/  # typecheck
just geocode                        # reverse geocode Address nodes (add --sample N for quick test)
just geocode --sample 500           # test run on 500 random addresses (no separate command needed)
just prepare-linz                   # transform LINZ shapefile into a cached parquet file
just enrich                         # post-load enrichment (share %)
just entity-resolution              # entity resolution pipeline
just load-db                        # drop + reload Neo4j graph (expects NZ_CO_DATA_DIR set, see docker-compose.yml)
just fetch <num>                    # fetch company from NZBN API
just dagster-dev                    # Dagster dev UI for the medallion pipeline (http://localhost:3000)
just pipeline <yyyymm>               # materialize bronze/silver/gold for one snapshot month, e.g. just pipeline 202611
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
- Imports: single-line per import, `combine-as-imports`, known-first-party `["nz-companies-office", "data_ingestion", "machine_learning"]`.
- **Object Oriented Programming**: use classes with single responsibility, prefer composition over inheritance, encapsulate related data and behaviour.
- **Design patterns**: follow established patterns (Strategy, Factory, Repository, etc.) where appropriate. Keep interfaces clean and documented.
- **Unit tests**: always create or update unit tests for every new function, class, or behaviour change. Tests must be deterministic and isolated (no network/DB calls).
- **Logging**: always use the `logging` module with `logger = logging.getLogger(__name__)` at module level. Use `colorlog` for coloured console output where appropriate.

## Architecture

- Source: `src/nz_companies_office/` (CLI, Neo4j graph loading/entity resolution) plus two top-level packages, not nested under `src/`: `data_ingestion/` (Dagster/DuckDB medallion pipeline) and `machine_learning/` (GNN link-prediction pipeline: `builder`, `extractor`, `features`, `split`, `link_predictor`, `trainer`, `embeddings`). All three are declared as package roots for the single `nz-companies-office` distribution in `pyproject.toml`'s `[tool.hatch.build.targets.wheel]`. (Note: `src/nz_companies_office/domain/models.py` — plain dataclasses — is unrelated to the `machine_learning` package; same English word, different things.)
- CLI entrypoint: `nz-companies-office = "nz_companies_office.cli.main:run"` (in `pyproject.toml`).
- Subcommands: `fetch`, `csv-fetch`, `load-db`, `er`, `enrich`, `prepare-linz`, `geocode`. (`fetch`/`csv-fetch` are unwired stubs — see `.specs/codebase/CONCERNS.md`.)
- Medallion orchestration: `data_ingestion/` (Dagster `Definitions` in `definitions.py`, assets in `assets/{bronze,silver,gold,graph}.py`), driven by `.sql` files in `data_ingestion/sql/{bronze,silver,gold}/`. It imports `nz_companies_office.config.SETTINGS` and `nz_companies_office.graph.loader` (the final `graph_load` asset drops/reloads Neo4j) — a cross-package dependency, expected to be unpicked once a real `knowledge_graph` package exists.
- ML pipeline: `machine_learning/` — only consumed from `notebooks/application/*.py` and `notebooks/06_exploring_embeddings.py` (no CLI/justfile wiring). Imports `nz_companies_office.config.SETTINGS` for all data/checkpoint paths.
- Data dirs (`data/raw/`, `data/bronze/`, `data/silver/`, `data/gold/`, `data/processed/`, `data/staging/`, `data/model_features/`) are git-ignored inside (track only `.gitignore`).

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
