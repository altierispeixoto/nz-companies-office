# Medallion Architecture — Stack & Tooling Decisions

Mirrors `.specs/project/STATE.md` AD-001 through AD-007. Written to `docs/` before implementation per project convention.

| Area | Choice | Rejected alternatives |
| --- | --- | --- |
| Storage layout | New `data/bronze/`, `data/silver/`, `data/gold/` directories | Reusing `data/raw`/`staging`/`processed` with reinterpreted meaning |
| Transform engine | DuckDB, SQL files under `sql/{bronze,silver,gold}/` | Polars DataFrame API; a DuckDB+Polars split |
| Storage format | Plain partitioned Parquet (`snapshot_month=<yyyymm>`) | Apache Iceberg (pyiceberg) — rejected as overkill at this scale (single operator, ~1-2M rows/table, no concurrent writers) |
| Change tracking | SCD2-style gold fact tables, built now | Deferring until the Capital Map raise-feed feature actually starts |
| Orchestration | Dagster (`dagster`, `dagster-webserver`, `dagster-duckdb`) | DVC pipelines (dependency removed — unused, no `dvc.yaml` existed); Snakemake; plain `justfile`-only |
| Validation | Dagster `@asset_check` | pandera; dbt-style SQL tests |
| NZBN validation policy | Quarantine to `_rejects` sidecar + reject-rate threshold check | Hard-fail the asset; silently drop invalid rows |
| Gold freshness | Per-table independent "latest" | Global cross-table watermark/readiness gate |
| Neo4j load source | Gold → flat CSV re-export, feeding the existing `LOAD CSV` Cypher scripts | Rewriting Cypher to read Parquet via APOC |

Full design detail: `architecture.md` in this directory (mirrors `.specs/features/medallion-architecture/design.md`). Task breakdown: `.specs/features/medallion-architecture/tasks.md`.
