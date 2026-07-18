"""Tests for the Neo4j connection manager."""

from __future__ import annotations

from unittest.mock import MagicMock
from unittest.mock import patch

import pytest
from neo4j import NotificationSeverity

from nz_companies_office.db.connection import close_driver
from nz_companies_office.db.connection import get_driver


def _make_mock_driver(*args: object, **kwargs: object) -> MagicMock:  # noqa: ARG001
    """Factory that returns a plain MagicMock (no spec) for Neo4j driver."""
    return MagicMock()


@pytest.fixture(autouse=True)
def reset_driver() -> None:
    """Reset the singleton driver before and after each test."""
    close_driver()
    yield
    close_driver()


def test_get_driver_uses_settings() -> None:
    """get_driver reads URI, user, password from SETTINGS."""
    with (
        patch("nz_companies_office.db.connection.SETTINGS") as mock_settings,
        patch("nz_companies_office.db.connection.GraphDatabase.driver") as mock_driver,
    ):
        mock_settings.neo4j_uri = "bolt://custom:7687"
        mock_settings.neo4j_user = "custom_user"
        mock_settings.neo4j_password = "custom_pass"  # noqa: S105
        driver = get_driver()
        mock_driver.assert_called_once_with(
            "bolt://custom:7687",
            auth=("custom_user", "custom_pass"),
            notifications_min_severity=NotificationSeverity.WARNING,
        )
        assert driver == mock_driver.return_value


def test_get_driver_singleton() -> None:
    """Multiple calls to get_driver return the same instance."""
    with (
        patch("nz_companies_office.db.connection.GraphDatabase.driver") as mock_driver,
    ):
        first = get_driver()
        second = get_driver()
        mock_driver.assert_called_once()
        assert first is second


def test_close_driver() -> None:
    """close_driver closes the underlying Neo4j driver."""
    with (
        patch("nz_companies_office.db.connection.GraphDatabase.driver") as mock_driver,
    ):
        get_driver()
        close_driver()
        mock_driver.return_value.close.assert_called_once()


def test_get_driver_defaults() -> None:
    """get_driver falls back to SETTINGS defaults."""
    with (
        patch("nz_companies_office.db.connection.SETTINGS") as mock_settings,
        patch("nz_companies_office.db.connection.GraphDatabase.driver") as mock_driver,
    ):
        mock_settings.neo4j_uri = "bolt://localhost:7687"
        mock_settings.neo4j_user = "neo4j"
        mock_settings.neo4j_password = "password"  # noqa: S105
        get_driver()
        mock_driver.assert_called_once_with(
            "bolt://localhost:7687",
            auth=("neo4j", "password"),
            notifications_min_severity=NotificationSeverity.WARNING,
        )


def test_close_driver_resets_singleton() -> None:
    """After close_driver, the next get_driver creates a fresh instance."""
    with (
        patch("nz_companies_office.db.connection.GraphDatabase.driver") as mock_driver,
    ):
        mock_driver.side_effect = _make_mock_driver
        first = get_driver()
        close_driver()
        second = get_driver()
        expected_call_count = 2
        assert mock_driver.call_count == expected_call_count
        assert first is not second
