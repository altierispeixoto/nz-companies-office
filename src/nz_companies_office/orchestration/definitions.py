"""Dagster Definitions entry point for the bronze/silver/gold medallion pipeline.

Load with ``dagster dev -f src/nz_companies_office/orchestration/definitions.py``
or ``dagster asset materialize -f src/nz_companies_office/orchestration/definitions.py``.
"""

from dagster import Definitions

from nz_companies_office.orchestration.assets.bronze import bronze_companies_core_data
from nz_companies_office.orchestration.assets.gold import gold_company_dim
from nz_companies_office.orchestration.assets.gold import gold_company_dim_uniqueness_check
from nz_companies_office.orchestration.assets.gold import gold_company_status_changes
from nz_companies_office.orchestration.assets.gold import gold_export_companies_csv
from nz_companies_office.orchestration.assets.silver import silver_company
from nz_companies_office.orchestration.assets.silver import silver_company_reject_rate_check
from nz_companies_office.orchestration.resources import duckdb_resource

defs = Definitions(
    assets=[
        bronze_companies_core_data,
        silver_company,
        gold_company_dim,
        gold_company_status_changes,
        gold_export_companies_csv,
    ],
    asset_checks=[
        silver_company_reject_rate_check,
        gold_company_dim_uniqueness_check,
    ],
    resources={"duckdb": duckdb_resource},
)
