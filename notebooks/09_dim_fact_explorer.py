# ---
# marimo-version: 0.23.9
# license: Apache-2.0
# ---

import marimo

__generated_with = "0.23.10"
app = marimo.App(width="full")


@app.cell
def _():
    import sys
    from pathlib import Path

    import altair as alt
    import marimo as mo

    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import _duckdb_helpers as dh

    return alt, dh, mo


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    # Gold dim/fact explorer

    **Pick any gold dimension or fact table and browse it directly: schema,
    row count, snapshot-month coverage, and the actual rows. Reads Parquet via
    DuckDB -- no Dagster or Neo4j needed.**

    Dimension tables are current-state (one row per key, unpartitioned). Fact
    tables are SCD2 change events, partitioned by the snapshot month the
    change was *detected* in (`sql/gold/{dims,facts}/`).
    """)
    return


@app.cell
def _(mo):
    kind_picker = mo.ui.dropdown(options=["dim", "fact"], value="dim", label="Kind")
    kind_picker
    return (kind_picker,)


@app.cell
def _(dh, kind_picker, mo):
    _names = dh.GOLD_DIMS if kind_picker.value == "dim" else dh.GOLD_FACTS
    name_picker = mo.ui.dropdown(options=_names, value=_names[0], label="Table")
    name_picker
    return (name_picker,)


@app.cell
def _(dh, kind_picker, name_picker):
    table_path = (
        dh.gold_dim_path(name_picker.value) if kind_picker.value == "dim" else dh.gold_fact_glob(name_picker.value)
    )
    row_total = dh.row_count(table_path)
    dh.create_view("t", table_path)
    return row_total, table_path


@app.cell(hide_code=True)
def _(kind_picker, mo, name_picker, row_total):
    mo.md(
        f"""
        ## `gold_{name_picker.value}`

        **{row_total:,} rows** ({"all materialized months" if kind_picker.value == "fact" else "current state"}).
        Available in the ad hoc query section below as the view **`t`**.
        """,
    )
    return


@app.cell
def _(dh, mo, table_path):
    schema_content = mo.vstack(
        [
            mo.md("Column names/types, via DuckDB's `DESCRIBE`."),
            mo.ui.table(dh.describe(table_path), page_size=20),
        ],
    )
    return (schema_content,)


@app.cell
def _(alt, dh, kind_picker, mo, table_path):
    if kind_picker.value == "fact":
        _by_month = dh.query(
            f"SELECT snapshot_month, count(*) AS n FROM read_parquet('{table_path}', hive_partitioning = false) "
            "GROUP BY snapshot_month ORDER BY snapshot_month",
        )
        _chart = (
            alt.Chart(_by_month)
            .mark_bar(color="#2a78d6")
            .encode(
                x=alt.X("snapshot_month:O", title="Snapshot month"),
                y=alt.Y("n:Q", title="Rows"),
                tooltip=["snapshot_month", "n"],
            )
            .properties(width="container", height=220)
        )
        coverage_content = mo.ui.altair_chart(_chart)
    else:
        coverage_content = mo.md("*Dimension tables are unpartitioned -- no per-month breakdown.*")
    return (coverage_content,)


@app.cell
def _(dh, mo, table_path):
    rows_content = mo.vstack(
        [
            mo.md(
                "Sortable/searchable in the table UI (click a column header to sort, use the "
                "search box to filter). Capped at 2,000 rows for responsiveness -- narrow down "
                "with the ad hoc query section for anything larger.",
            ),
            mo.ui.table(dh.sample(table_path, limit=2000), page_size=25, selection=None),
        ],
    )
    return (rows_content,)


@app.cell
def _(mo):
    sql_box = mo.ui.text_area(value="SELECT * FROM t LIMIT 50", label="SQL", full_width=True)
    return (sql_box,)


@app.cell
def _(dh, mo, sql_box, table_path):
    # table_path (unused directly) forces this cell to rerun when the picked table changes,
    # re-registering the `t` view it depends on.
    try:
        _result = dh.query(sql_box.value)
        query_result = mo.ui.table(_result, page_size=25) if len(_result) else mo.md("*No rows*")
    except Exception as exc:  # surfaced inline instead of crashing the notebook
        query_result = mo.md(f"**Query error:** `{exc}`")
    return (query_result,)


@app.cell
def _(mo, query_result, sql_box):
    query_content = mo.vstack(
        [
            mo.md(
                "Runs against the view `t` (the table picked above) -- e.g. "
                "`SELECT entity_status, count(*) FROM t GROUP BY 1 ORDER BY 2 DESC`.",
            ),
            sql_box,
            query_result,
        ],
    )
    return (query_content,)


@app.cell
def _(coverage_content, mo, query_content, rows_content, schema_content):
    mo.accordion(
        {
            "Schema": schema_content,
            "Snapshot-month coverage": coverage_content,
            "Rows (sample)": rows_content,
            "Ad hoc query": query_content,
        },
        multiple=True,
    )
    return


if __name__ == "__main__":
    app.run()
