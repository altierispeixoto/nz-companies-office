"""Tests for entity resolution helper functions."""

from __future__ import annotations

import pytest

from nz_companies_office.graph.entity_resolution import _trigram_jaccard


class TestTrigramJaccard:
    """Tests for the trigram Jaccard similarity function."""

    def test_identical_names(self) -> None:
        """Identical names should score 1.0."""
        assert _trigram_jaccard("John Smith", "John Smith") == pytest.approx(1.0)

    def test_completely_different(self) -> None:
        """Completely unrelated names should score near 0."""
        score = _trigram_jaccard("Alice Wong", "Zachary Zhu")
        assert score < 0.3  # noqa: PLR2004

    def test_subset_match(self) -> None:
        """A shorter name that is a subset of a longer name scores > 0.5."""
        score = _trigram_jaccard("Melissa Clark", "Melissa Alice Clark")
        assert score >= 0.5  # noqa: PLR2004

    def test_middle_name_variant(self) -> None:
        """Names differing only by a middle name should score highly."""
        score = _trigram_jaccard("Harpreet Kaur", "Harpreet Singh Kaur")
        assert score >= 0.6  # noqa: PLR2004

    def test_case_insensitive(self) -> None:
        """Case differences should not affect the score."""
        assert _trigram_jaccard("JOHN SMITH", "john smith") == pytest.approx(1.0)

    def test_single_char_names(self) -> None:
        """Very short names should still produce a valid score."""
        score = _trigram_jaccard("A B", "A B")
        assert score == pytest.approx(1.0)

    def test_empty_strings(self) -> None:
        """Empty strings are identical, so Jaccard = 1.0."""
        assert _trigram_jaccard("", "") == pytest.approx(1.0)

    def test_symmetric(self) -> None:
        """Jaccard similarity should be symmetric."""
        a, b = "David Lee", "David John Lee"
        assert _trigram_jaccard(a, b) == pytest.approx(_trigram_jaccard(b, a))

    def test_common_last_name(self) -> None:
        """Two different people with the same common last name score low."""
        score = _trigram_jaccard("John Smith", "James Smith")
        assert score < 0.6  # noqa: PLR2004

    def test_high_confidence_threshold(self) -> None:
        """A name with a middle initial added should exceed high-confidence threshold."""
        score = _trigram_jaccard("John Smith", "John A Smith")
        assert score >= 0.65  # noqa: PLR2004


class TestNameKeyLogic:
    """Tests for the name_key computation (first initial + last name, uppercased).

    The Cypher query computes: toUpper(split(normalized_name, ' ')[0])
                                + toUpper(split(normalized_name, ' ')[-1])
    We replicate this in Python to test the logic.
    """

    @staticmethod
    def _name_key(name: str) -> str:
        words = name.split(" ")
        return words[0][0].upper() + words[-1].upper()

    def test_two_words(self) -> None:
        """Two-word name produces first-letter + last-name."""
        assert self._name_key("John Smith") == "JSMITH"

    def test_three_words(self) -> None:
        """Three-word name uses first letter of first word and full last word."""
        assert self._name_key("Melissa Alice Clark") == "MCLARK"

    def test_single_word(self) -> None:
        """Single-word name uses first and last character of the word."""
        assert self._name_key("Singh") == "SSINGH"


class TestIsPersonLogic:
    """Tests for the is_person detection (name contains at least one lowercase letter)."""

    @staticmethod
    def _is_person(name: str) -> bool:
        return bool(__import__("re").search(r"[a-z]", name))

    def test_normal_name_is_person(self) -> None:
        """Normal mixed-case name is a person."""
        assert self._is_person("John Smith") is True

    def test_all_uppercase_is_not_person(self) -> None:
        """All-uppercase string (e.g., company code) is not a person."""
        assert self._is_person("ABC LIMITED") is False

    def test_lowercase_only_is_person(self) -> None:
        """All-lowercase name is still a person."""
        assert self._is_person("john smith") is True

    def test_mixed_case_with_numbers(self) -> None:
        """Name with numbers and uppercase is not a person if no lowercase."""
        assert self._is_person("ABC123") is False
