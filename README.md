# NZ Companies Office — Graph Analytics

[![Python](https://img.shields.io/badge/python-3.10%20%7C%203.11%20%7C%203.12-blue)](pyproject.toml)
[![Neo4j](https://img.shields.io/badge/Neo4j-5--community-008CC1)](docker-compose.yml)
[![Code style: ruff](https://img.shields.io/badge/code%20style-ruff-000000.svg)](https://github.com/astral-sh/ruff)
[![Marimo](https://img.shields.io/badge/notebooks-marimo-FFD43B)](https://marimo.io)

Analyse the full New Zealand Companies Register — 1.8M companies, 1.2M directors,
1.6M shareholders — as a Neo4j property graph. This project loads monthly bulk
CSV exports from the [NZ Companies Office](https://www.companiesoffice.govt.nz/),
builds a co-investment network, and runs graph data science pipelines to detect
entity resolution patterns, suspicious nominee structures, and investor
classification.

## Key Findings

### Network Structure

- **909,517 Shareholder nodes** and **20,528 undirected CO_INVESTS_WITH edges**
  (weighted by shared company count, threshold ≥5) form the co-investment graph.
- The graph is **highly fragmented** — **903,559 disconnected components**, largest
  contains just **183 nodes**. No giant component exists.
- **Four Louvain communities** dominate: NZ Trustee Services (183), HSBC/JPMorgan
  institutional nominees (114), CLM Trustees (39), Bailey Ingham Trustees (36).
  Beyond that, only discrete property syndicates and VC groups.
- **Most entities have only 1 or 2 co-investors** — the network is a collection of
  thousands of isolated real-world syndicates.

### Dominant Players

- **NEW ZEALAND TRUSTEE SERVICES LIMITED** appears in **659 companies** — the
  top shareholder by reach. A professional trustee providing registered office and
  nominee director services.
- **Bronwyn Ann HANTZ** appears in **665 director positions** — likely a
  professional director or nominee. Three other DOG TRUSTEE directors (David GRAY,
  Tara WRATTEN, Brendan WOOD) each sit on **574–589 companies**.
- **DOG TRUSTEE LIMITED** holds shares in **317 companies but has zero
  co-investors** — a pure nominee "black box". Approximately **30 such entities**
  identified across the graph.
- **"The Landings at Stonefields"** has **184 shareholders** — the most of any
  company. Unit-title apartment blocks dominate the list.
- **NZ Trustee Services has 62 co-investor connections** (highest degree
  centrality). Individuals like Benjamin CAESAR and Rebecca DICKIE rank highest
  by PageRank — they bridge communities within corporate trustee clusters.

### Suspicious Patterns

- **30 nominee "black box" entities** (DOG TRUSTEE, Custodial Services, etc.)
  that sit in thousands of companies with zero co-investors — no one else
  invests in the same companies, confirming they hold shares as a service.
- **1,105 companies** registered at a single address (18 Maniapoto Street,
  Otorohanga) — the Bailey Ingham Trustees network.
- **The Singh/Kaur/Wei anomaly** — individuals with extreme industry
  diversification across **17 of 19 ANZSIC divisions simultaneously**, suggesting
  nominee or director-for-hire operations.
- **Harpreet KAUR** tops the shareholder-director gap list — **133 shareholder
  positions** but only a handful of directorships.

### Entity Resolution

- **604,671 exact name matches** between Shareholder and Director datasets after
  normalising whitespace (the CSV export uses double spaces in shareholder names
  and single spaces in director names).
- **105,080 Person nodes** created via trigram fuzzy matching, with **117,499
  `SAME_AS` relationships** connecting variant names to canonical identities.
- **33,918 verified** by company overlap (matched Shareholder–Director pairs that
  share at least one company), **30,025 false positives** (common names like
  Singh, Kaur, Patel), **291 strong matches** (≥3 shared companies).
- **~75K directors** who don't appear as shareholders — they run companies but
  don't own shares in them.

### Investor Classification (Proof of Concept)

- **16 hand-labeled seed entities** across 4 classes (VC=4, PROPERTY=5,
  TRUSTEE=3, ACCOUNTING=4) used to classify **9,257 shareholders** in the
  co-investment graph.
- **Node2Vec embeddings alone are insufficient** — they predict mostly one class
  because structural similarity doesn't capture scale.
- **FastRP embeddings + features (company_count, co_investor_count, PageRank)
  at α=0.7** produces the most balanced distribution (the current `best_label`
  configuration).
- Seed count (16) is the limiting factor — the model would benefit from **50–100
  labeled examples per class**. This is a proof of concept for cohort analysis,
  not production classification.

## Architecture

```
NZ Companies Office (monthly CSV)
         │
         ▼
    LOAD CSV ──► Neo4j 5-community ──► marimo notebooks
         │         (APOC + GDS)            │
         │                                 ├─ 01: Mapping the network
         │                                 ├─ 02: Co-investment patterns
         ▼                                 ├─ 03: Communities & influence
    Python CLI                              ├─ 04: Entity resolution
    (NZBN API fallback)                     └─ 05: Predicting investor types
```

Data flows: bulk CSVs downloaded monthly → loaded into Neo4j via `LOAD CSV` with
Cypher scripts → queried and visualised in marimo notebooks. An optional NZBN API
client provides single-company lookups as a fallback.

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
| **Trustee** | Not a distinct CSV type — a *role* that emerges from patterns. Trustee companies (e.g. "NZ TRUSTEE SERVICES LIMITED", "DOG TRUSTEE 2011 LIMITED") appear as shareholders or directors but hold assets on behalf of beneficiaries, not for their own benefit. These are the "black box" entities in our analysis. |
| **Nominee** | An entity that holds shares or acts as director on behalf of the beneficial owner. Institutional nominees (HSBC, JPMorgan) appear as shareholders for custodial services. |
| **Insolvency Practitioner** | An appointed liquidator, receiver, or voluntary administrator. Recorded with appointment/vacation dates, type of insolvency, and organisation. |

### Roles & Relationships

| Relationship | Description |
|-------------|-------------|
| **Holds shares in** | A shareholder owns a parcel of shares in a company. Properties: number of shares, start date, share status, parcel ID, extensive shareholding flag. Nodes: `(:Shareholder)-[:HOLDS_SHARES_IN]->(:Company)`. |
| **Directs** | A director is appointed to manage a company. Properties: appointment date, ASIC cross-ref. Nodes: `(:Director)-[:DIRECTS]->(:Company)`. |
| **Co-invests with** | Two shareholders who both hold shares in the same company. Inferred from shared company membership. Weighted by the number of common companies. Nodes: `(:Shareholder)-[:CO_INVESTS_WITH]-(:Shareholder)`. |
| **Has address** | A company's registered office, address for service, or public address. Properties: start date, full address lines, postcode, country. Nodes: `(:Company)-[:HAS_ADDRESS]->(:Address)`. |
| **Is same as** | Connects a variant name (e.g. "Harpreet  KAUR" with double spaces) to the canonical Person identity. Created by entity resolution. Properties: trigram score, confidence (high/medium/low), company overlap count, verified flag. Nodes: `(:Shareholder)-[:SAME_AS]->(:Person)`. |

### Names & Entity Resolution

The Shareholder CSV uses **double spaces** between first and last names
("Harpreet  KAUR") while the Director CSV uses single spaces ("Harpreet KAUR").
The `normalized_name` property collapses both to single-space form. Entity
resolution proceeds in stages:

1. **Exact match** — `normalized_name` equality between Shareholder and Director
   (604,671 matches).
2. **Trigram fuzzy match** — for non-exact matches, a `name_key` pre-filter
   (first word + last word, e.g. "HKaur") reduces the candidate pool, then
   trigram Jaccard similarity at thresholds ≥0.5 (low), ≥0.55 (medium), ≥0.65
   (high).
3. **Verification** — each match is checked for company overlap (do the matched
   Shareholder and Director share at least one company?).

### Co-investment Network

The `CO_INVESTS_WITH` relationship is the central abstraction for graph analysis.
Two shareholders co-invest if they both hold shares in the same company. The
weight is their number of common companies. At threshold ≥5, the graph has
909,517 nodes and 20,528 edges — but is highly fragmented (903,559 disconnected
components, max component size 183 nodes).

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

`coinvest` — 909,517 Shareholder nodes, 20,528 undirected `CO_INVESTS_WITH`
edges (weighted), projected with `UNDIRECTED` orientation.

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

# 3. Start Neo4j
just neo4j-up

# 4. Load the data
just neo4j-import-csv

# 5. Explore in notebooks
just marimo
```

### Commands

| Command | Description |
|---------|-------------|
| `just setup` | Create venv + sync + pre-commit install |
| `just neo4j-up` | Start Neo4j via Docker Compose |
| `just neo4j-down` | Stop Neo4j |
| `just neo4j-import-csv` | Load all CSV data (pipes script to cypher-shell) |
| `just fetch <number>` | Fetch a single company from NZBN API + load to Neo4j |
| `just marimo` | Start marimo notebook server at `http://127.0.0.1:2718/` |
| `just run pytest` | Run test suite |
| `just run ruff check .` | Lint |
| `just run ruff format .` | Format |
| `just run mypy src/` | Type-check |

### Notebooks

All notebooks are in `notebooks/` and use the shared helpers in
`_neo4j_helpers.py` (`run_query()`, `mo_table()`).

| Notebook | What it covers |
|----------|---------------|
| `01_mapping_the_network.py` | Graph overview, node/relationship counts, top shareholders/directors, most-shared companies, entity type & status distribution, WCC components, fragmentation |
| `02_co_investment_patterns.py` | Top co-investor pairs (NZ Trustee Services + Evan Mackenzie, 155 shared), trustee black boxes (DOG TRUSTEE, 317 companies, zero co-investors), Otorohanga cluster (1,105 at one address), Singh/Kaur/Wei industry diversification anomaly |
| `03_communities_and_influence.py` | Louvain (max 183 nodes), degree centrality (NZ Trustee Services: 62), PageRank (individuals > firms), clustering coefficient (Icehouse VC: 0.12, NZ Trustee: 0.27), Node2Vec similarity search |
| `04_entity_resolution.py` | Double-space problem, exact matching (604,671), name_key pre-filter (~676K shareholders), trigram fuzzy matching at ≥0.5/0.55/0.65, Person graph (105,080 nodes, 117,499 SAME_AS), verification by company overlap (33,918 verified, 30,025 false positives) |
| `05_predicting_investor_types.py` | 16 hand-labeled seeds (VC/PROPERTY/TRUSTEE/ACCOUNTING), Node2Vec vs FastRP embeddings, feature normalisation (company_count max 659, co_investor_count max 62, PageRank max 10.66), combined score at α=0.7, 9,257 shareholders classified |

## Project Structure

```
├── data/raw/<yyyymm>/        # Monthly CSV exports
├── notebooks/                 # marimo walkthrough notebooks
│   ├── __init__.py
│   ├── _neo4j_helpers.py     # Shared run_query() + mo_table() helpers
│   ├── 01_mapping_the_network.py
│   ├── 02_co_investment_patterns.py
│   ├── 03_communities_and_influence.py
│   ├── 04_entity_resolution.py
│   └── 05_predicting_investor_types.py
├── scripts/
│   ├── neo4j_load_csv.cypher # Canonical LOAD CSV import (10 steps, ~3 min)
│   └── explore_graph.cypher  # 810+ analysis queries
├── src/nz_companies_office/
│   ├── cli/main.py           # CLI entry point
│   ├── clients/nzbn.py       # NZBN API client
│   ├── db/
│   │   ├── connection.py     # Neo4j connection manager
│   │   └── repository.py     # save_company(), get_company_by_number()
│   ├── loaders/csv_loader.py # CsvCompanyLoader (iter_all(), get_company())
│   └── models/company.py     # Pydantic data models
├── tests/                    # Unit tests (33 pass)
├── integration/              # Integration tests (require Neo4j)
├── docker-compose.yml        # Neo4j 5-community + APOC + GDS
├── justfile                  # Task runner recipes
├── pyproject.toml            # Dependencies and project config
└── ruff.toml                 # Lint/format configuration
```

## Testing

```bash
# Quick gate
ruff check src/nz_companies_office/ tests/test_*.py integration/
pytest tests/ -v

# Full gate
ruff check . && ruff format --check . && mypy src/ && pytest tests/ --cov
```

## Code Quality

- **Lint**: ruff with ALL rules enabled (line-length 120)
- **Types**: mypy with `--disallow-untyped-defs`
- **Docs**: Google-style docstrings
- **Format**: ruff format (double quotes, Black-compatible)
- **Pre-commit**: ruff (lint+format), mypy, nbstripout, gitleaks, sqlfluff
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

## License

MIT
