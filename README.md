# NZ Companies Office — Graph Analytics

[![Python](https://img.shields.io/badge/python-3.10%20%7C%203.11%20%7C%203.12-blue)](pyproject.toml)
[![Neo4j](https://img.shields.io/badge/Neo4j-5--community-008CC1)](docker-compose.yml)
[![DuckDB](https://img.shields.io/badge/medallion-DuckDB%20%2B%20Dagster-FFF000)](docs/medallion-architecture/architecture.md)
[![Code style: ruff](https://img.shields.io/badge/code%20style-ruff-000000.svg)](https://github.com/astral-sh/ruff)
[![Marimo](https://img.shields.io/badge/notebooks-marimo-FFD43B)](https://marimo.io)

Analyse the full New Zealand Companies Register — 1.8M companies, 1.2M directors,
1.6M shareholders — as a Neo4j property graph. This project loads monthly bulk
CSV exports from the [NZ Companies Office](https://www.companiesoffice.govt.nz/),
builds a co-investment network, and runs graph data science pipelines to detect
entity resolution patterns, suspicious nominee structures, and investor
classification.

## Architecture

```
NZ Companies Office (monthly CSV, data/raw/<yyyymm>/)
         │
         ▼                                     ── all orchestrated by Dagster, DuckDB SQL ──
   bronze (Parquet, 1:1 copy)                    (data_ingestion/sql/bronze/*.sql)
         │
         ▼
   silver (typed, validated, deduped)             (data_ingestion/sql/silver/*.sql)
         │
         ▼
   gold (current-state dims + SCD2 change facts)  (data_ingestion/sql/gold/{dims,facts}/*.sql)
         │
         ▼
   gold export (flat CSV)                         (data_ingestion/sql/gold/export/*.sql)
         │
         ▼
   graph_load asset ──► scripts/csv/*.cypher ──► Neo4j 5-community ──► marimo notebooks
                          (cypher-shell)             (APOC + GDS)
```

Data flows: bulk CSVs downloaded monthly → a bronze/silver/gold medallion pipeline
(Dagster + DuckDB, top-level `data_ingestion/` package) cleans, types, validates,
and historizes every previously-loaded source table → a flat CSV export → a Dagster
asset drops and reloads Neo4j from that export, running `scripts/csv/*.cypher` → queried
and visualised in marimo notebooks (see [Notebooks](#notebooks) below). Browse the
silver/gold Parquet layers directly with `just duckdb-ui` (DuckDB's local web UI). The 5
"other entity register" CSVs (charitable trust boards, retirement villages, etc.) were
never loaded into the graph and remain untouched. See
`docs/medallion-architecture/architecture.md` and `stack.md` for the full design and
tooling rationale.

### Dagster orchestration

Everything from bronze through the Neo4j load is one Dagster asset graph in the
top-level `data_ingestion/` package (not nested under `src/` — it's a separate
package root declared in `pyproject.toml`), auto-discovered from the
`assets/{bronze,silver,gold,graph}.py` modules — adding a new `@asset` to one
of those files registers it in `definitions.py` automatically, nothing to wire
up by hand. It still imports `nz_companies_office.config.SETTINGS` and
`nz_companies_office.graph.loader` (for the `graph_load` asset) — a cross-package
dependency kept intentionally for now, to be unpicked once a real
`knowledge_graph` package exists.

| Asset group | Partitioning | What it does |
|---|---|---|
| `bronze` | By snapshot month (`StaticPartitionsDefinition`, discovered from `data/raw/<yyyymm>/` subdirectories — snapshots are dropped in manually, not a date range) | 1:1 typed copy of each raw CSV to Parquet |
| `silver` | By snapshot month | Validates, deduplicates, and historizes each bronze table; invalid rows are quarantined to a `_rejects` sidecar instead of failing the asset (guarded by a reject-rate `@asset_check`) |
| `gold_dims` | Unpartitioned — always recomputed from the full silver history (latest snapshot wins per key) | Current-state dimension tables |
| `gold_facts` | By snapshot month | SCD2 change-fact tables (what changed in this month's snapshot vs. the previous one) |
| `gold_export` | Unpartitioned — always targets the latest available snapshot month | Flat CSV export, one file per table, written to `data/gold/_neo4j_export/<month>/` |
| `graph` | Unpartitioned | The `graph_load` asset: drops and reloads Neo4j from that export directory, via the same `load_database()` that `just load-db` calls directly — one implementation of the drop-and-reload logic, not two |

All assets share a single DuckDB resource (`DuckDBResource(database=":memory:")`,
`data_ingestion/resources.py`) — there's no persisted `.duckdb` file; every asset
reads/writes explicit Parquet or CSV paths, so there's one less place for a path
to drift from what Dagster actually materialized.

**Running it:**

- `just dagster-dev` — the Dagster dev UI (`http://localhost:3000`): browse the
  full asset graph (including `graph_load`), materialize assets individually,
  inspect run history and asset-check results.
- `just pipeline <yyyymm>` — `dagster asset materialize --select '*' --partition <yyyymm>`.
  Materializes bronze/silver/gold_facts for that month *and*, in the same run,
  recomputes the unpartitioned gold_dims/gold_export/graph assets. The `graph_load`
  step only succeeds if Neo4j is already running with `NZ_CO_DATA_DIR` pointed at
  this run's export — otherwise it fails harmlessly while everything upstream
  still materializes; re-run `just pipeline <yyyymm>` (or just `just load-db`)
  once Neo4j is up to pick that step back up.
- `NZ_CO_DATA_DIR` must be set *before* starting Neo4j, pointed at the export
  directory a pipeline run already wrote, e.g.
  `NZ_CO_DATA_DIR=./data/gold/_neo4j_export/202611 just neo4j` (see
  `docker-compose.yml`). Each run gets its own per-month export directory rather
  than a fixed `latest/`, because Neo4j's official image chowns any bind-mounted
  directory to its internal user on first start — reusing one across runs would
  leave it unwritable from the host.

## Key Concepts

The NZ Companies Register records *entities* and their *roles*. Every row in the
bulk data is keyed by the **NZBN** (New Zealand Business Number), a unique
identifier assigned to each registered entity by the NZBN Register (MBIE).

### Entities

| Concept | Description |
|---------|-------------|
| **Company** | A legal entity registered under the Companies Act 1993. Has a unique NZBN and company number. Can be "Registered" or "Removed". Types include NZ Limited, Overseas ASIC, and others. |
| **Shareholder** | A person or legal entity that owns shares in a company. In the CSV data, a shareholder can be an individual, another company, or an "other entity" (trust, nominee, etc.). Each holding is a row with parcel details: number of shares, extensive shareholding flag, status, and start date. |
| **Director** | A person appointed to manage a company's affairs. The CSV records active directors only, with their full name, appointment start date, and whether they also direct an Australian company (ASIC cross-reference). |
| **Trustee** | Not a distinct CSV type — a *role* that emerges from patterns. Trustee companies appear as shareholders or directors but hold assets on behalf of beneficiaries, not for their own benefit. |
| **Nominee** | An entity that holds shares or acts as director on behalf of the beneficial owner. Institutional nominees (HSBC, JPMorgan) appear as shareholders for custodial services. |
| **Insolvency Practitioner** | An appointed liquidator, receiver, or voluntary administrator. Recorded with appointment/vacation dates, type of insolvency, and organisation. |

### Roles & Relationships

| Relationship | Description |
|-------------|-------------|
| **Holds shares in** | A shareholder owns a parcel of shares in a company. Properties: number of shares, start date, share status, parcel ID, extensive shareholding flag. Nodes: `(:Shareholder)-[:HOLDS_SHARES_IN]->(:Company)`. |
| **Directs** | A director is appointed to manage a company. Properties: appointment date, ASIC cross-ref. Nodes: `(:Director)-[:DIRECTS]->(:Company)`. |
| **Co-invests with** | Two shareholders who both hold shares in the same company. Inferred from shared company membership. Weighted by the number of common companies. Nodes: `(:Shareholder)-[:CO_INVESTS_WITH]-(:Shareholder)`. |
| **Has address** | A company's registered office, address for service, or public address. Properties: start date, full address lines, postcode, country. Nodes: `(:Company)-[:HAS_ADDRESS]->(:Address)`. |
| **Is same as** | Connects a variant name (e.g. "Jane  DOE" with double spaces) to the canonical Person identity. Created by entity resolution. Properties: trigram score, confidence (high/medium/low), company overlap count, verified flag. Nodes: `(:Shareholder)-[:SAME_AS]->(:Person)`. |

### Names & Entity Resolution

The Shareholder CSV uses **double spaces** between first and last names
("Jane  DOE") while the Director CSV uses single spaces ("Jane DOE"). The
`normalized_name` property collapses both to single-space form. Entity
resolution proceeds in stages:

1. **Exact match** — `normalized_name` equality between Shareholder and
   Director.
2. **Trigram fuzzy match** — for non-exact matches, a `name_key` pre-filter
   (first word + last word, e.g. "JDoe") reduces the candidate pool, then
   trigram Jaccard similarity at thresholds ≥0.5 (low), ≥0.55 (medium), ≥0.65
   (high).
3. **Verification** — each match is checked for company overlap (do the matched
   Shareholder and Director share at least one company?).

### Co-investment Network

The `CO_INVESTS_WITH` relationship is the central abstraction for graph analysis.
Two shareholders co-invest if they both hold shares in the same company. The
weight is their number of common companies; only pairs at or above a
configurable minimum shared-company threshold are materialized as edges (see
`02_co_investment_patterns.py`).

### Industry Classification

Companies optionally report a BIC (Business Industry Classification) code,
which maps to the ANZSIC system. These are stored as `:Industry` nodes with a
`code` property, linked via `[:HAS_INDUSTRY]` relationships. The CSV contains
2,708 unique industry codes across 1.8M companies.

### Entity Types

The `entity_type` property (not a separate node) classifies each company.
Common values from the data include standard NZ limited liability companies,
overseas companies (ASIC), and other legal forms. The `status` property tracks
whether the company is currently registered or has been removed.

## Data Catalog

The source data is a monthly snapshot from the [NZ Companies Office bulk data
service](https://www.companiesoffice.govt.nz/data-services/ways-to-get-our-data/bulk-data-help-guide/),
distributed as a zip containing 19 CSV files joined by the NZBN (New Zealand
Business Number).

### Core company data

| File | Rows | Description |
|------|------|-------------|
| `companies_core_data.csv` | 1.81M | All registered and removed companies: name, type, status, registration/removal date |
| `companies_director.csv` | 1.17M | Active directors of registered companies (name, appointment date, ASIC cross-ref) |
| `companies_shareholder.csv` | 1.59M | Active shareholders with parcel details: number of shares, extensive holding flag, address |
| `companies_address_for_service.csv` | — | Address for service for registered companies |
| `companies_registered_office_address.csv` | — | Registered office address (where company records are kept) |
| `companies_public_address.csv` | — | Public delivery, invoice, office and/or postal addresses |
| `companies_business_industry_classification.csv` | 2,708 | BIC codes (ANZSIC-based industry classification) |
| `companies_insolvency.csv` | 3,454 | Insolvency practitioner appointments (liquidation, receivership, voluntary administration) |
| `companies_trading_name.csv` | 143K | Public trading names |
| `companies_trading_area.csv` | 84 | Public trading areas |
| `companies_abn.csv` | — | Australian Business Numbers |
| `companies_gst.csv` | — | GST numbers |
| `companies_website.csv` | — | Public website addresses |

### Other entity registers

| File | Description |
|------|-------------|
| `other_incorporated_entities_core_data.csv` | Incorporated societies and limited partnerships |
| `charitable_trust_boards_core_data.csv` | Charitable trust boards |
| `unincorporated_entities_core_data.csv` | Sole traders, partnerships and trusts |
| `retirement_villages_core_data.csv` | Registered and cancelled retirement villages |
| `public_sector_entities_core_data.csv` | Central/local government, education, other public entities |
| `maori_business_identifier.csv` | Entities identified as Māori businesses on the NZBN register |

## Neo4j Graph Model

```
(Company) ◄──[:DIRECTS]── (Director)
    │                            ▲
    │                            │
    ├──[:HAS_INDUSTRY]──► (Industry)
    │                            │
    ├──[:HAS_ADDRESS]──► (Address)
    │                            │
    ├──[:HAS_TRADING_NAME]──► (TradingName)
    │                            │
    ├──[:HAS_TRADING_AREA]──► (TradingArea)
    │                            │
    └──[:HAS_INSOLVENCY]──► (Insolvency)
```

**Relationship properties** (all stored on edges, never on nodes):

- `[:HOLDS_SHARES_IN]` — shares, extensive_shareholding, start_date, sh_status,
  parcel_id, assignment_id
- `[:DIRECTS]` — appointed_on, asic_dir_yn
- `[:HAS_ADDRESS]` — since
- `[:HAS_INSOLVENCY]` — appointed_on, vacated_on, resolution_of_solvency
- `[:CO_INVESTS_WITH]` — weight (number of shared companies)
- `[:SAME_AS]` — score, confidence, company_overlap, verified

### GDS graph (in-memory)

`coinvest` — an in-memory GDS projection of the co-investment graph
(`:Shareholder` nodes, undirected weighted `CO_INVESTS_WITH` edges), used by
the community-detection, centrality, and embedding notebooks. Projected with
`UNDIRECTED` orientation (required for `gds.localClusteringCoefficient`).

## Getting Started

### Prerequisites

- Python 3.10+
- [uv](https://github.com/astral-sh/uv) package manager
- Docker (for Neo4j)

### Setup

```bash
# 1. Clone and install
git clone <repo>
cd nz-companies-office
uv venv
uv sync

# 2. Configure environment
cp .env-template .env
# Edit .env with your Neo4j credentials and NZBN API key (optional)

# 3. Drop a monthly snapshot under data/raw/<yyyymm>/, then run the medallion
#    pipeline for it: bronze -> silver -> gold -> gold CSV export. The final
#    graph_load step will fail here since Neo4j isn't up yet -- that's fine,
#    everything upstream of it still gets materialized.
just pipeline 202611

# 4. Start Neo4j, pointed at that run's export directory
NZ_CO_DATA_DIR=./data/gold/_neo4j_export/202611 just neo4j

# 5. Load the data (re-runs just the graph_load step against the now-running Neo4j)
just load-db

# 6. Explore in notebooks
just marimo
```

### Commands

| Command | Description |
|---------|-------------|
| `just setup` | Create venv + `uv sync` + pre-commit install |
| `just install` / `just update` | `uv sync` / `uv sync --upgrade` |
| `just run <cmd>` | Run any command inside the project venv (creates it first if missing) |
| `just activate` | Drop into a shell with the venv activated |
| `just neo4j` / `just neo4j-down` | Start / stop Neo4j via Docker Compose. `NZ_CO_DATA_DIR` must be set when starting (points at a `data/gold/_neo4j_export/<yyyymm>/` written by `just pipeline`) — see `docker-compose.yml` |
| `just load-db` | Canonical load: drops and reloads the full graph against the already-running Neo4j, running each `scripts/csv/*.cypher` step in order |
| `just neo4j-import-csv` | Legacy single-script load (pipes `scripts/neo4j_load_csv.cypher` directly to cypher-shell) — predates the medallion migration, not kept in sync with `scripts/csv/*.cypher`; prefer `just load-db` |
| `just fetch <number>` | Registered CLI subcommand, not yet wired to an NZBN API client — currently a no-op |
| `just entity-resolution` | Run the entity resolution pipeline (`er`) |
| `just enrich` | Post-load enrichment (shareholding percentages, majority flags) |
| `just enrich-industry-descriptions` | Set descriptions on Industry ancestor nodes from ANZSIC reference |
| `just prepare-linz` | Transform the LINZ shapefile into a cached Parquet file |
| `just geocode [--sample N]` | Reverse geocode Address nodes using LINZ NZ Addresses |
| `just dagster-dev` | Dagster dev UI for the full asset graph — bronze/silver/gold plus the Neo4j `graph_load` asset (`http://localhost:3000`) |
| `just pipeline <yyyymm>` | `dagster asset materialize --select '*' --partition <yyyymm>`: bronze → silver → gold → gold export for that month, then attempts `graph_load` (fails harmlessly if Neo4j isn't running yet) |
| `just duckdb-ui` | Browse `silver.*`/`gold.*` Parquet tables in DuckDB's local web UI (`http://localhost:4213`) |
| `just marimo` / `just marimo-ml` | Start marimo notebook server at `http://127.0.0.1:2718/`, over `notebooks/` or `machine_learning/notebooks/` respectively |
| `just run pytest` | Run the test suite (`tests/`) |
| `just run ruff check .` / `just run ruff format .` | Lint / format |
| `just run mypy src/ data_ingestion/ machine_learning/` | Type-check |
| `just clean` | Remove the virtual environment |

### Notebooks

All notebooks are marimo apps (`just marimo` for `notebooks/`, `just marimo-ml`
for `machine_learning/notebooks/`). The numbered `notebooks/` root-level files
form the research narrative and share `_neo4j_helpers.py` (`run_query()`,
`mo_table()`); `workshop-gnn/` is a separate, self-contained sub-series.

| Notebook | What it covers |
|----------|---------------|
| `00_load_database.py` | Reset utility: checks Neo4j connectivity, drops GDS in-memory graphs, wipes all nodes before a fresh `just load-db` |
| `01_mapping_the_network.py` | Graph overview: node/relationship counts, entity type & status distribution, top shareholders/directors by reach, connected-component analysis |
| `02_co_investment_patterns.py` | Co-investment pattern mining: top co-investor pairs, nominee "black-box" detection (high company count, zero co-investors), shared-address clustering, cross-industry diversification outliers |
| `03_communities_and_influence.py` | Louvain community detection, degree centrality, PageRank, clustering coefficient, and Node2Vec similarity search over the co-investment graph |
| `04_entity_resolution.py` | Entity resolution between Shareholder and Director names: exact match + trigram fuzzy matching, verified by company overlap |
| `05_entity_resolution_v2.py` | Second entity-resolution pass: multi-blocking candidate generation + a trained classifier, instead of 04's single trigram threshold |
| `05_predicting_investor_types.py` | Investor-type classification proof of concept: hand-labeled seed entities, Node2Vec vs FastRP embeddings combined with graph features |

The GNN/link-prediction notebooks live under `machine_learning/notebooks/`
instead, alongside the pipeline code they import (see
[Project Structure](#project-structure)):

| Notebook | What it covers |
|----------|---------------|
| `06_exploring_embeddings.py` | Extracts the graph from Neo4j, builds exploration features and a `HeteroData` object for GNN embedding experiments |
| `07_visualize_embeddings.py` | Embedding Atlas visualization of the learned node embeddings (reads `06`'s output) |

`machine_learning/notebooks/application/` — a small end-to-end GNN link-prediction app:
`00_dataset.py` (build the training dataset), `01_link_prediction.py` (train/evaluate),
`02_interactive_testing.py` (interactive inference over a saved checkpoint).

`notebooks/workshop-gnn/` — a standalone teaching series on graph neural networks,
independent of this project's data: `01_gnn_foundations.py`, `02_gcn.py`, `03_gat.py`,
`04_graphsage.py`, `05_graph_classification.py`, `06_advanced_gnn.py`.

## Project Structure

```
├── data/raw/<yyyymm>/         # Monthly CSV exports (git-ignored)
├── data/{bronze,silver,gold}/ # Medallion pipeline output (git-ignored)
├── data/{staging,processed,model_features}/ # LINZ cache, geocode exports, ML features (git-ignored)
├── data_ingestion/              # Dagster/DuckDB medallion pipeline — top-level package, not under src/
│   ├── definitions.py          # Dagster Definitions entry point
│   ├── resources.py            # Shared DuckDBResource(":memory:")
│   ├── partitions.py           # Snapshot-month StaticPartitionsDefinition
│   ├── sql.py                  # read_sql() — resolves data_ingestion/sql/*.sql
│   ├── catalog.py              # SILVER_TABLES/GOLD_DIMS/GOLD_FACTS name registry
│   ├── assets/{bronze,silver,gold,graph}.py # the asset graph (graph.py calls into
│   │                            # nz_companies_office.graph.loader for the Neo4j load)
│   └── sql/
│       ├── bronze/*.sql       # 1:1 typed copy of each raw source table
│       ├── silver/*.sql       # Validated, deduplicated, historized tables
│       └── gold/
│           ├── dims/*.sql     # Current-state dimensions
│           ├── facts/*.sql    # SCD2 change-fact tables
│           └── export/*.sql   # Flat CSV export feeding scripts/csv/*.cypher
├── machine_learning/            # GNN link-prediction pipeline — top-level package, not under src/
│   ├── builder.py              # build_hetero_data() — assembles the PyG HeteroData graph
│   ├── extractor.py            # GraphExtractor — pulls the investor graph from Neo4j (cached .pt)
│   ├── features.py             # Node feature tensors (one-hots, degree, embeddings)
│   ├── split.py                 # Train/val/test edge splitting + negative sampling
│   ├── link_predictor.py       # HeteroEncoder/Decoder/LinkPredictor (torch nn.Modules)
│   ├── trainer.py              # LinkPredictorTrainer — training loop, AUC/AP eval, checkpointing
│   ├── embeddings.py           # Sentence-transformers industry-description embeddings
│   │                            # (no CLI/justfile wiring — only consumed by notebooks/ below)
│   └── notebooks/              # marimo apps — `just marimo-ml` (see Notebooks section above)
│       ├── 06_exploring_embeddings.py
│       ├── 07_visualize_embeddings.py
│       └── application/       # GNN link-prediction mini-app (00_dataset, 01_link_prediction,
│                                # 02_interactive_testing)
├── notebooks/                  # marimo apps — `just marimo` (see Notebooks section above)
│   ├── _neo4j_helpers.py      # Shared run_query() + mo_table() helpers
│   ├── 00_load_database.py .. 05_predicting_investor_types.py
│   └── workshop-gnn/           # Standalone GNN teaching series
├── scripts/
│   ├── csv/*.cypher           # Canonical per-entity LOAD CSV steps, run in order by `just load-db`
│   │                          # (src/nz_companies_office/graph/loader.py::load_csv)
│   ├── neo4j_load_csv.cypher  # Legacy single-script load, piped by `just neo4j-import-csv`;
│   │                          # predates the medallion migration, prefer `just load-db`
│   ├── explore_graph.cypher   # Analysis queries
│   └── duckdb_ui.py           # Launches DuckDB's UI over the silver/gold Parquet layers
├── src/nz_companies_office/
│   ├── cli/main.py            # CLI entry point (`nz-companies-office`)
│   ├── config.py              # Settings dataclass (paths, Neo4j/thresholds config)
│   ├── db/                    # Neo4j connection manager + repository
│   ├── graph/                 # Entity resolution, enrichment, geocoding, industry descriptions, loader
│   ├── domain/models.py       # Dataclasses for Company/Director/Shareholder/Address (unrelated to
│   │                          # the top-level machine_learning/ package, despite the shared name)
│   ├── loaders/csv_loader.py  # Legacy bulk CSV loader, used only by the unwired `csv-fetch` CLI stub
│   └── utils/device.py        # torch device selection (CPU/CUDA/MPS)
├── tests/                     # Unit tests, no network/DB calls
├── docs/medallion-architecture/ # Design + stack decisions for the bronze/silver/gold pipeline
├── docker-compose.yml         # Neo4j 5-community + APOC + GDS
├── justfile                   # Task runner recipes
├── pyproject.toml             # Dependencies and project config
└── ruff.toml                  # Lint/format configuration
```

## Testing

```bash
# Quick gate
just run ruff check .
just run pytest -v

# Full gate
just run ruff check . && just run ruff format --check . && just run mypy src/ data_ingestion/ machine_learning/ && just run pytest --cov
```

All tests live under `tests/`, are deterministic, and make no network/DB calls.

## Code Quality

- **Lint**: ruff with ALL rules enabled (line-length 120)
- **Types**: mypy with `--disallow-untyped-defs`
- **Docs**: Google-style docstrings
- **Format**: ruff format (double quotes, Black-compatible)
- **Pre-commit** (`.pre-commit-config.yaml`): standard pre-commit-hooks (trailing
  whitespace, large files, merge conflicts, etc.), ruff (lint + format), mypy.
  SQLFluff is configured (`sql/.sqlfluff`, DuckDB dialect) but not yet wired into
  pre-commit.
- **Conventional commits**: `feat:`, `fix:`, `perf:`, etc.

## Key Architecture Decisions

- **LOAD CSV is canonical** — bulk import via Cypher LOAD CSV (~3 min), not
  Python. Old Python bulk code removed.
- **Indexes before LOAD CSV** — create indexes on MERGE-key properties *before*
  loading data. Without indexes, each MERGE does a full node scan.
- **Edge properties only** — relationship attributes stored on edges, not nodes.
  Node-level storage was corrupted by last-row-wins on multi-row shareholders.
- **Entity resolution at Cypher level** — two-stage matching: `name_key`
  (first+last word) for indexed pre-filter, then trigram Jaccard for scoring.
  Exact matches use `normalized_name` directly.
- **GDS graph projected with `UNDIRECTED`** — required for
  `gds.localClusteringCoefficient`.
- **DETACH DELETE must be batched** — single-transaction DELETE on 6M nodes
  exceeds heap. Use `apoc.periodic.iterate` with batchSize 50K.
- **Memory**: Neo4j configured for 24G heap, 4G page cache, 16G transaction max
  (system with 62GB RAM).
- **No persisted DuckDB file for the medallion pipeline** — bronze/silver/gold
  assets read and write Parquet paths directly (`:memory:` connections) rather
  than a shared `.duckdb` file, so there's one less place for a path to drift
  from what Dagster actually materialized. See `docs/medallion-architecture/architecture.md`.
- **Entity resolution stays Neo4j-native** — DuckDB has no equivalent trigram
  similarity function, so the `er` pipeline (stage 04/05 above) is not part of
  the medallion migration.

## License

MIT
