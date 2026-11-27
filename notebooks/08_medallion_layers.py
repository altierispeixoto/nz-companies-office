# ---
# marimo-version: 0.23.9
# license: Apache-2.0
# ---

import marimo

__generated_with = "0.23.10"
app = marimo.App(width="full")

# Validated categorical palette (dataviz skill, references/palette.md) -- fixed
# slot order, never cycled. Status colors are the separate, reserved pair.
_BLUE = "#2a78d6"
_ORANGE = "#eb6834"
_AQUA = "#1baf7a"
_YELLOW = "#eda100"
_GOOD = "#0ca30c"
_CRITICAL = "#d03b3b"


@app.cell
def _():
    import sys
    from pathlib import Path

    import altair as alt
    import marimo as mo
    import polars as pl

    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import _duckdb_helpers as dh

    return alt, dh, mo, pl


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    # Evaluating the medallion layers

    **Bronze → silver → gold for the NZ Companies Office medallion pipeline
    (`.specs/features/medallion-architecture/`). This notebook checks that each
    layer is doing its job: bronze preserves row counts, silver's NZBN
    validation rejects only a small fraction, gold's SCD2 facts detect real
    changes, and gold's address dedup actually collapses duplicates.**

    Reads the Parquet files directly with DuckDB -- no Dagster or Neo4j needed.
    """)
    return


@app.cell
def _(dh, mo):
    months = dh.available_months()
    mo.md(f"**Materialized snapshot months:** {', '.join(months)}")
    return (months,)


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## 1. Row-count trends: bronze vs. silver

    Bronze is a 1:1 copy of the raw CSV (no filtering), so bronze and silver
    row counts should track closely -- a growing gap means silver's
    dedup/validation (or a `WHERE` filter, e.g. `company_industry`'s ANZSIC
    code check) is doing more work than expected.
    """)
    return


@app.cell
def _(mo):
    table_picker = mo.ui.dropdown(
        options=[
            "companies_core_data",
            "companies_director",
            "companies_shareholder",
            "companies_business_industry_classification",
            "companies_trading_name",
            "companies_trading_area",
            "companies_insolvency",
        ],
        value="companies_core_data",
        label="Bronze table",
    )
    table_picker
    return (table_picker,)


@app.cell
def _(alt, dh, mo, table_picker):
    # bronze table name -> matching silver table name (see sql/silver/*.sql)
    _silver_name = {
        "companies_core_data": "company",
        "companies_director": "director",
        "companies_shareholder": "shareholder",
        "companies_business_industry_classification": "company_industry",
        "companies_trading_name": "trading_name",
        "companies_trading_area": "trading_area",
        "companies_insolvency": "insolvency",
    }[table_picker.value]

    _trend = dh.query(
        f"""
        WITH bronze AS (
            SELECT snapshot_month, count(*) AS n, 'bronze' AS layer
            FROM read_parquet('{dh.bronze_glob(table_picker.value)}', hive_partitioning = true)
            GROUP BY snapshot_month
        ),
        silver AS (
            SELECT snapshot_month, count(*) AS n, 'silver' AS layer
            FROM read_parquet('{dh.silver_glob(_silver_name)}', hive_partitioning = false)
            GROUP BY snapshot_month
        )
        SELECT snapshot_month, n, layer FROM bronze
        UNION ALL
        SELECT snapshot_month, n, layer FROM silver
        ORDER BY snapshot_month
        """,
    )

    _chart = (
        alt.Chart(_trend)
        .mark_line(point=True, strokeWidth=2)
        .encode(
            x=alt.X("snapshot_month:O", title="Snapshot month"),
            y=alt.Y("n:Q", title="Row count"),
            color=alt.Color(
                "layer:N",
                title="Layer",
                scale=alt.Scale(domain=["bronze", "silver"], range=["#2a78d6", "#eb6834"]),
            ),
            tooltip=["snapshot_month", "layer", "n"],
        )
        .properties(width="container", height=300, title=f"{table_picker.value}: bronze vs. silver row count")
    )
    mo.ui.altair_chart(_chart)
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## 2. NZBN reject rate

    `silver_company` quarantines rows with a malformed NZBN to a `_rejects`
    sidecar instead of dropping them. The asset check fails above **0.1%**
    (`REJECT_RATE_THRESHOLD` in `silver.py`) -- same threshold shown here.
    """)
    return


@app.cell
def _(alt, dh, mo, pl):
    _rejects = dh.query(
        f"""
        WITH good AS (
            SELECT snapshot_month, count(*) AS n
            FROM read_parquet('{dh.silver_company_glob()}', hive_partitioning = false)
            GROUP BY snapshot_month
        ),
        bad AS (
            SELECT snapshot_month, count(*) AS n
            FROM read_parquet('{dh.silver_company_rejects_glob()}', hive_partitioning = false)
            GROUP BY snapshot_month
        )
        SELECT
            good.snapshot_month,
            bad.n AS rejects,
            good.n + bad.n AS total,
            100.0 * bad.n / (good.n + bad.n) AS reject_pct
        FROM good
        JOIN bad ON good.snapshot_month = bad.snapshot_month
        ORDER BY good.snapshot_month
        """,
    )
    _threshold_pct = 0.1
    _rejects = _rejects.with_columns(
        status=pl.when(pl.col("reject_pct") <= _threshold_pct).then(pl.lit("pass")).otherwise(pl.lit("fail")),
    )

    _bars = (
        alt.Chart(_rejects)
        .mark_bar()
        .encode(
            x=alt.X("snapshot_month:O", title="Snapshot month"),
            y=alt.Y("reject_pct:Q", title="Reject rate (%)"),
            color=alt.Color(
                "status:N",
                title="vs. 0.1% threshold",
                scale=alt.Scale(domain=["pass", "fail"], range=["#0ca30c", "#d03b3b"]),
            ),
            tooltip=["snapshot_month", "rejects", "total", alt.Tooltip("reject_pct:Q", format=".4f")],
        )
    )
    _rule = (
        alt.Chart(dh.query("SELECT 0.1 AS threshold"))
        .mark_rule(strokeDash=[4, 4], color="#52514e")
        .encode(y="threshold:Q")
    )
    _labels = _bars.mark_text(dy=-8, color="#0b0b0b").encode(text=alt.Text("reject_pct:Q", format=".4f"))

    mo.ui.altair_chart(
        (_bars + _rule + _labels).properties(width="container", height=280, title="NZBN reject rate by month")
    )
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## 3. SCD2 change facts

    Month-over-month change detection (`gold/facts/*.sql`). The earliest
    available month always has zero rows here (no prior month to diff
    against) -- see `MED-04`'s documented edge case.
    """)
    return


@app.cell
def _(alt, dh, mo):
    _share_changes = dh.query(
        f"""
        SELECT snapshot_month, change_type, count(*) AS n
        FROM read_parquet('{dh.gold_fact_glob("shareholding_changes")}', hive_partitioning = false)
        GROUP BY snapshot_month, change_type
        ORDER BY snapshot_month
        """,
    )
    _chart = (
        alt.Chart(_share_changes)
        .mark_bar()
        .encode(
            x=alt.X("snapshot_month:O", title="Snapshot month"),
            y=alt.Y("n:Q", title="Change events"),
            color=alt.Color(
                "change_type:N",
                title="Change type",
                scale=alt.Scale(
                    domain=["NEW", "INCREASED", "DECREASED", "EXITED"],
                    range=["#2a78d6", "#eb6834", "#1baf7a", "#eda100"],
                ),
            ),
            tooltip=["snapshot_month", "change_type", "n"],
        )
        .properties(width="container", height=300, title="gold_shareholding_changes by type")
    )
    mo.ui.altair_chart(_chart)
    return


@app.cell
def _(alt, dh, mo):
    _director_changes = dh.query(
        f"""
        SELECT snapshot_month, change_type, count(*) AS n
        FROM read_parquet('{dh.gold_fact_glob("director_appointment_changes")}', hive_partitioning = false)
        GROUP BY snapshot_month, change_type
        ORDER BY snapshot_month
        """,
    )
    _chart = (
        alt.Chart(_director_changes)
        .mark_bar()
        .encode(
            x=alt.X("snapshot_month:O", title="Snapshot month"),
            y=alt.Y("n:Q", title="Change events"),
            color=alt.Color(
                "change_type:N",
                title="Change type",
                scale=alt.Scale(domain=["APPOINTED", "RESIGNED"], range=["#2a78d6", "#eb6834"]),
            ),
            tooltip=["snapshot_month", "change_type", "n"],
        )
        .properties(width="container", height=300, title="gold_director_appointment_changes by type")
    )
    mo.ui.altair_chart(_chart)
    return


@app.cell
def _(alt, dh, mo):
    _status_changes = dh.query(
        f"""
        SELECT snapshot_month, count(*) AS n
        FROM read_parquet('{dh.gold_fact_glob("company_status_changes")}', hive_partitioning = false)
        GROUP BY snapshot_month
        ORDER BY snapshot_month
        """,
    )
    _chart = (
        alt.Chart(_status_changes)
        .mark_bar(color="#2a78d6")
        .encode(
            x=alt.X("snapshot_month:O", title="Snapshot month"),
            y=alt.Y("n:Q", title="Companies with a status change"),
            tooltip=["snapshot_month", "n"],
        )
        .properties(width="container", height=260, title="gold_company_status_changes per month")
    )
    mo.ui.altair_chart(_chart)
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## 4. Share percentage distribution

    `gold_shareholding` computes `share_percentage`/`is_majority` in SQL --
    the same arithmetic `graph/enrichment.py`'s Cypher does today. The dashed
    line marks the 50% majority threshold.
    """)
    return


@app.cell
def _(alt, dh, mo):
    _shares = dh.query(
        f"SELECT share_percentage FROM read_parquet('{dh.gold_dim_path('shareholding')}', hive_partitioning = false)"
    )
    _hist = (
        alt.Chart(_shares)
        .mark_bar(color="#2a78d6")
        .encode(
            x=alt.X("share_percentage:Q", bin=alt.Bin(maxbins=40), title="Share percentage"),
            y=alt.Y("count():Q", title="Shareholdings"),
            tooltip=[alt.Tooltip("count():Q", title="count")],
        )
    )
    _rule = (
        alt.Chart(dh.query("SELECT 50.0 AS majority"))
        .mark_rule(strokeDash=[4, 4], color="#d03b3b")
        .encode(x="majority:Q")
    )
    mo.ui.altair_chart(
        (_hist + _rule).properties(
            width="container", height=300, title="Distribution of share_percentage (latest per shareholder+company)"
        )
    )
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## 5. Address dedup ratio

    `gold_address_dim` merges on `(street, city, country)` -- the same key
    `Address` nodes merge on in Cypher. One physical address shared across
    companies (or address types) should collapse to a single row here.
    """)
    return


@app.cell
def _(alt, dh, mo, months):
    _latest = months[-1]
    _raw = dh.row_count(dh.silver_glob("company_address"))
    _unique = dh.row_count(dh.gold_dim_path("address_dim"))
    _dedup = dh.query(
        f"SELECT 'company_address rows (all months)' AS what, {_raw} AS n "
        f"UNION ALL SELECT 'unique addresses (address_dim)', {_unique}",
    )
    _chart = (
        alt.Chart(_dedup)
        .mark_bar()
        .encode(
            x=alt.X("what:N", title=None, sort=None),
            y=alt.Y("n:Q", title="Rows"),
            color=alt.Color(
                "what:N",
                legend=None,
                scale=alt.Scale(
                    domain=["company_address rows (all months)", "unique addresses (address_dim)"],
                    range=["#2a78d6", "#1baf7a"],
                ),
            ),
            tooltip=["what", "n"],
        )
        .properties(width="container", height=260, title="Address rows vs. deduped addresses")
    )
    _ratio = 100.0 * (1 - _unique / _raw) if _raw else 0.0
    mo.vstack(
        [
            mo.ui.altair_chart(_chart),
            mo.md(
                f"**{_ratio:.1f}%** of address rows collapsed into a shared address (latest materialization: {_latest})."
            ),
        ]
    )
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## 6. Cross-layer row-count table

    Every migrated table's bronze vs. silver row count, side by side, for the
    latest snapshot month -- a quick scan for anything unexpectedly dropped.
    """)
    return


@app.cell
def _(dh, mo, months, pl):
    _latest = months[-1]
    # companies_registered_office_address/address_for_service/public_address are
    # deliberately excluded: silver_company_address unions all three (see
    # sql/silver/company_address.sql), so no single bronze table maps 1:1 to it --
    # that fan-in is exactly what section 5's dedup ratio looks at instead.
    _pairs = [
        ("companies_core_data", "company"),
        ("companies_director", "director"),
        ("companies_shareholder", "shareholder"),
        ("companies_business_industry_classification", "company_industry"),
        ("companies_trading_name", "trading_name"),
        ("companies_trading_area", "trading_area"),
        ("companies_insolvency", "insolvency"),
        ("companies_abn", "company_abn"),
        ("companies_gst", "company_gst"),
        ("companies_website", "company_website"),
        ("maori_business_identifier", "maori_business_identifier"),
    ]
    _rows = []
    for _bronze_name, _silver_name in _pairs:
        _b = dh.row_count(str(dh.bronze_glob(_bronze_name)).replace("snapshot_month=*", f"snapshot_month={_latest}"))
        _s = dh.row_count(str(dh.silver_glob(_silver_name)).replace("snapshot_month=*", f"snapshot_month={_latest}"))
        _rows.append({"bronze_table": _bronze_name, "silver_table": _silver_name, "bronze_rows": _b, "silver_rows": _s})

    mo.ui.table(pl.DataFrame(_rows), page_size=15)
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ---

    **Next:** rerun this after `just pipeline <month>` picks up a new snapshot,
    or after Increment 2's open items (see `.specs/project/ROADMAP.md`) land --
    the `HAS_ADDRESS` collapsing and `11_corporate_links` performance findings
    both live downstream of gold, past what this notebook checks.
    """)
    return


if __name__ == "__main__":
    app.run()
