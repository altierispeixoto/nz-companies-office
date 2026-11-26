"""Dagster asset wrapping the existing Neo4j graph-load pipeline."""

from dagster import AssetExecutionContext
from dagster import asset

from nz_companies_office.config import SETTINGS
from nz_companies_office.graph.loader import load_database
from nz_companies_office.orchestration.assets.gold import gold_export_companies_business_industry_classification
from nz_companies_office.orchestration.assets.gold import gold_export_companies_core_data
from nz_companies_office.orchestration.assets.gold import gold_export_companies_director
from nz_companies_office.orchestration.assets.gold import gold_export_companies_insolvency
from nz_companies_office.orchestration.assets.gold import gold_export_companies_shareholder
from nz_companies_office.orchestration.assets.gold import gold_export_companies_trading_area
from nz_companies_office.orchestration.assets.gold import gold_export_companies_trading_name
from nz_companies_office.orchestration.assets.gold import gold_export_company_address


@asset(
    group_name="graph",
    deps=[
        gold_export_companies_core_data,
        gold_export_companies_director,
        gold_export_companies_shareholder,
        gold_export_company_address,
        gold_export_companies_business_industry_classification,
        gold_export_companies_trading_name,
        gold_export_companies_trading_area,
        gold_export_companies_insolvency,
    ],
)
def graph_load(context: AssetExecutionContext) -> None:
    """Drop and reload the Neo4j graph from the gold-exported CSVs.

    Thin wrapper around ``graph/loader.py::load_database()`` -- the same function
    `just load-db` calls -- so there is exactly one implementation of the
    drop-and-reload pipeline, not a duplicate. Requires Neo4j (the
    ``NZ_CO_DATA_DIR`` env var pointing at this run's gold export directory,
    e.g. ``./data/gold/_neo4j_export/<month>``) to be running and reachable.
    """
    load_database(root_dir=SETTINGS.project_root)
    context.add_output_metadata({"root_dir": str(SETTINGS.project_root)})
