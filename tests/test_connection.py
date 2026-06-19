"""Tests for the Neo4j connection manager."""

from __future__ import annotations

from unittest.mock import MagicMock
from unittest.mock import patch

import pytest

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


def test_get_driver_uses_env_vars() -> None:
    """get_driver reads URI, user, password from environment."""
    with (
        patch("nz_companies_office.db.connection.os.environ.get") as mock_get,
        patch("nz_companies_office.db.connection.GraphDatabase.driver") as mock_driver,
    ):
        mock_get.side_effect = ["bolt://custom:7687", "custom_user", "custom_pass"]
        driver = get_driver()
        mock_driver.assert_called_once_with(
            "bolt://custom:7687",
            auth=("custom_user", "custom_pass"),
        )
        assert driver == mock_driver.return_value


def test_get_driver_singleton() -> None:
    """Multiple calls to get_driver return the same instance."""
    with (
        patch("nz_companies_office.db.connection.os.environ.get") as mock_get,
        patch("nz_companies_office.db.connection.GraphDatabase.driver") as mock_driver,
    ):
        mock_get.return_value = None
        first = get_driver()
        second = get_driver()
        mock_driver.assert_called_once()
        assert first is second


def test_close_driver() -> None:
    """close_driver closes the underlying Neo4j driver."""
    with (
        patch("nz_companies_office.db.connection.os.environ.get") as mock_get,
        patch("nz_companies_office.db.connection.GraphDatabase.driver") as mock_driver,
    ):
        mock_get.return_value = None
        get_driver()
        close_driver()
        mock_driver.return_value.close.assert_called_once()


def test_get_driver_defaults() -> None:
    """get_driver falls back to localhost defaults when env vars are not set."""
    with (
        patch("nz_companies_office.db.connection.os.environ.get") as mock_get,
        patch("nz_companies_office.db.connection.GraphDatabase.driver") as mock_driver,
    ):
        mock_get.side_effect = lambda _key, default=None: default
        get_driver()
        mock_driver.assert_called_once_with(
            "bolt://localhost:7687",
            auth=("neo4j", "password"),
        )


def test_close_driver_resets_singleton() -> None:
    """After close_driver, the next get_driver creates a fresh instance."""
    with (
        patch("nz_companies_office.db.connection.os.environ.get") as mock_get,
        patch("nz_companies_office.db.connection.GraphDatabase.driver") as mock_driver,
    ):
        mock_get.side_effect = lambda _key, default=None: default
        mock_driver.side_effect = _make_mock_driver
        first = get_driver()
        close_driver()
        second = get_driver()
        expected_call_count = 2
        assert mock_driver.call_count == expected_call_count
        assert first is not second
