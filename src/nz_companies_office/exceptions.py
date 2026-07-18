"""Custom exception hierarchy for the Companies Office project."""

from __future__ import annotations


class CompaniesOfficeError(Exception):
    """Base exception for all project-specific errors."""


class Neo4jConnectionError(CompaniesOfficeError):
    """Raised when Neo4j is unreachable or authentication fails."""


class Neo4jQueryError(CompaniesOfficeError):
    """Raised when a Cypher query fails unexpectedly."""


class GeocodeError(CompaniesOfficeError):
    """Raised during reverse-geocoding pipeline failures."""


class LinzNotFoundError(GeocodeError):
    """Raised when the LINZ shapefile or cache is missing."""
