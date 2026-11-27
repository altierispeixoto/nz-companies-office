"""Canonical registry of silver and gold table names.

Single source of truth for anything that needs to enumerate the medallion
layers without re-deriving the list from ``sql/{silver,gold}/*.sql`` file
names (notebooks, the DuckDB UI launcher, etc.), so they can't drift apart.
"""

from __future__ import annotations

SILVER_TABLES: list[str] = [
    "company",
    "company_abn",
    "company_address",
    "company_gst",
    "company_industry",
    "company_website",
    "director",
    "insolvency",
    "maori_business_identifier",
    "shareholder",
    "trading_area",
    "trading_name",
]

GOLD_DIMS: list[str] = [
    "company_dim",
    "shareholding",
    "director_dim",
    "address_dim",
    "company_address",
    "company_industry",
    "company_trading_name",
    "company_trading_area",
    "company_insolvency",
]

GOLD_FACTS: list[str] = [
    "company_status_changes",
    "shareholding_changes",
    "director_appointment_changes",
]
