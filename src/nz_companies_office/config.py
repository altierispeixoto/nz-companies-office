"""Centralised configuration with environment variable fallbacks."""

from __future__ import annotations

import os
from dataclasses import dataclass
from dataclasses import field
from pathlib import Path


def _project_root() -> Path:
    return Path(__file__).resolve().parent.parent.parent


@dataclass(frozen=True)
class Settings:
    """Application-wide settings with defaults and env overrides."""

    # Paths
    project_root: Path = field(default_factory=_project_root)
    data_dir: Path = field(default_factory=lambda: _project_root() / "data")

    # Neo4j
    neo4j_uri: str = field(default_factory=lambda: os.environ.get("NEO4J_URI", "bolt://localhost:7687"))
    neo4j_user: str = field(default_factory=lambda: os.environ.get("NEO4J_USER", "neo4j"))
    neo4j_password: str = field(default_factory=lambda: os.environ.get("NEO4J_PASSWORD", "password"))

    # LINZ shapefile
    linz_shp_dir: Path = field(default_factory=lambda: _project_root() / "data" / "raw" / "lds-nz-addresses-SHP")
    linz_shp_filename: str = "nz-addresses.shp"

    # LINZ cache (Parquet)
    linz_cache_dir: Path = field(default_factory=lambda: _project_root() / "data" / "staging")
    linz_cache_filename: str = "linz-addresses-cache.parquet"
    linz_norm_cache_filename: str = "linz-addresses-cache-norm.parquet"

    # Geocode export
    geocode_export_dir: Path = field(default_factory=lambda: _project_root() / "data" / "processed")
    geocode_export_filename: str = "geocoded-addresses.csv"
    geocode_result_filename: str = "reverse-geocode-results.csv"

    # Raw company CSV directory
    raw_data_dir: Path = field(default_factory=lambda: _project_root() / "data" / "raw")

    # Entity resolution thresholds
    er_trigram_min_score: float = 0.55
    er_trigram_high_confidence: float = 0.65
    er_min_company_count: int = 3

    # Geocode (reverse) thresholds
    geocode_trigram_min_score: float = 0.7
    geocode_trigram_high_confidence: float = 0.85
    geocode_lsh_num_perm: int = 128
    geocode_lsh_threshold: float = 0.5

    @property
    def linz_shp_path(self) -> Path:
        """Full path to the LINZ shapefile."""
        return self.linz_shp_dir / self.linz_shp_filename

    @property
    def linz_cache_path(self) -> Path:
        """Full path to the LINZ parquet cache."""
        return self.linz_cache_dir / self.linz_cache_filename

    @property
    def linz_norm_cache_path(self) -> Path:
        """Full path to the normalized LINZ parquet cache."""
        return self.linz_cache_dir / self.linz_norm_cache_filename

    @property
    def geocode_export_path(self) -> Path:
        """Full path to the geocode export CSV."""
        return self.geocode_export_dir / self.geocode_export_filename

    @property
    def geocode_result_path(self) -> Path:
        """Full path to the geocode result CSV."""
        return self.geocode_export_dir / self.geocode_result_filename


SETTINGS = Settings()
