"""Dagster Definitions entry point for the bronze/silver/gold medallion pipeline.

Load with ``dagster dev -f data_ingestion/definitions.py``
or ``dagster asset materialize -f data_ingestion/definitions.py``.

Assets and checks are auto-discovered from the ``assets`` package's modules
(``bronze``, ``silver``, ``gold``, ``graph``) rather than imported one by one,
so adding a new asset to one of those modules registers it here automatically.
"""

from dagster import Definitions
from dagster import load_asset_checks_from_modules
from dagster import load_assets_from_modules

from data_ingestion.assets import bronze
from data_ingestion.assets import gold
from data_ingestion.assets import graph
from data_ingestion.assets import silver
from data_ingestion.resources import duckdb_resource

_ASSET_MODULES = [bronze, silver, gold, graph]

defs = Definitions(
    assets=load_assets_from_modules(_ASSET_MODULES),
    asset_checks=load_asset_checks_from_modules(_ASSET_MODULES),
    resources={"duckdb": duckdb_resource},
)
