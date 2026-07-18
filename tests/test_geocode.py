"""Tests for reverse geocoding helpers."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pandas as pd
import pytest

if TYPE_CHECKING:
    from pathlib import Path

from nz_companies_office.graph.geocode import _build_lsh_index
from nz_companies_office.graph.geocode import _lsh_match_row
from nz_companies_office.graph.geocode import _normalize_text
from nz_companies_office.graph.geocode import _parse_street_number
from nz_companies_office.graph.geocode import _pick_city
from nz_companies_office.graph.geocode import _resolve_csv_dir
from nz_companies_office.graph.geocode import _score_candidates
from nz_companies_office.graph.geocode import _stage_exact
from nz_companies_office.graph.geocode import _stage_name_fallback
from nz_companies_office.graph.geocode import _trigram_jaccard
from nz_companies_office.graph.geocode import _trigrams
from nz_companies_office.graph.geocode import extract_addresses_from_csv
from nz_companies_office.graph.geocode import normalize


class TestResolveCsvDir:
    """Tests for the _resolve_csv_dir helper."""

    def test_returns_dir_with_csvs(self, tmp_path: Path) -> None:
        """When CSVs live directly in the dir, it is returned as-is."""
        (tmp_path / "companies_shareholder.csv").write_text("a,b\n1,2\n")
        assert _resolve_csv_dir(tmp_path) == tmp_path

    def test_picks_most_recent_dated_subdir(self, tmp_path: Path) -> None:
        """A dated export subdir is auto-selected (most recent wins)."""
        old = tmp_path / "202601"
        old.mkdir()
        new = tmp_path / "202607"
        new.mkdir()
        (new / "companies_shareholder.csv").write_text("a,b\n1,2\n")
        assert _resolve_csv_dir(tmp_path) == new

    def test_returns_original_when_empty(self, tmp_path: Path) -> None:
        """With no CSVs anywhere, the original dir is returned."""
        empty = tmp_path / "empty"
        empty.mkdir()
        assert _resolve_csv_dir(empty) == empty


class TestNormalizeText:
    """Tests for the _normalize_text helper."""

    def test_lowercase_and_strip(self) -> None:
        """Whitespace is stripped and text lowercased."""
        assert _normalize_text("  HELLO WORLD  ") == "hello world"

    def test_macron_normalisation(self) -> None:
        """Maori macrons are replaced with ASCII equivalents."""
        assert _normalize_text("Pōneke") == "poneke"

    def test_abbreviation_expansion(self) -> None:
        """Common street type abbreviations are expanded."""
        assert _normalize_text("High St") == "high street"

    def test_multiple_abbreviations(self) -> None:
        """Multiple abbreviations in one string are all expanded."""
        assert _normalize_text("St Rd Ave") == "street road avenue"

    def test_punctuation_stripped(self) -> None:
        """Punctuation is removed except hyphens."""
        assert _normalize_text("123, Some Rd.") == "123 some road"

    def test_hyphen_preserved(self) -> None:
        """Hyphens within words are preserved."""
        assert _normalize_text("well-known place") == "well-known place"

    def test_none_returns_empty(self) -> None:
        """None input returns empty string."""
        assert _normalize_text(None) == ""

    def test_empty_string(self) -> None:
        """Empty string returns empty string."""
        assert _normalize_text("") == ""


class TestParseStreetNumber:
    """Tests for the _parse_street_number helper."""

    def test_number_prefix(self) -> None:
        """Leading number is extracted as street number."""
        assert _parse_street_number("16 Amritsar Street") == ("16", "amritsar street")

    def test_number_with_letter(self) -> None:
        """Number with suffix letter (42A) is kept together."""
        assert _parse_street_number("42A Queen Street") == ("42A", "queen street")

    def test_no_number(self) -> None:
        """No number prefix returns empty string for number."""
        assert _parse_street_number("Queen Street") == ("", "queen street")

    def test_po_box(self) -> None:
        """PO Box addresses return empty number."""
        assert _parse_street_number("PO Box 123") == ("", "po box 123")

    def test_none(self) -> None:
        """None returns empty strings."""
        assert _parse_street_number(None) == ("", "")

    def test_empty(self) -> None:
        """Empty returns empty strings."""
        assert _parse_street_number("") == ("", "")

    def test_two_word_street(self) -> None:
        """Multi-word street name after number is preserved."""
        assert _parse_street_number("10 Victoria Street West") == ("10", "victoria street west")


class TestTrigramJaccard:
    """Tests for the trigram Jaccard similarity function."""

    def test_identical(self) -> None:
        """Identical strings score 1.0."""
        assert _trigram_jaccard("queen street", "queen street") == pytest.approx(1.0)

    def test_completely_different(self) -> None:
        """Unrelated strings score near 0."""
        score = _trigram_jaccard("abc", "xyz")
        assert score < 0.3  # noqa: PLR2004

    def test_similar_street_names(self) -> None:
        """Street name and abbreviation score moderately high."""
        score = _trigram_jaccard("victoria street", "victoria st")
        assert score >= 0.5  # noqa: PLR2004

    def test_case_insensitive(self) -> None:
        """Case differences do not affect score."""
        assert _trigram_jaccard("QUEEN ST", "queen st") == pytest.approx(1.0)

    def test_empty_strings(self) -> None:
        """Two empty strings score 0.0 (guard returns early)."""
        assert _trigram_jaccard("", "") == pytest.approx(0.0)

    def test_one_empty(self) -> None:
        """One empty string scores 0.0."""
        assert _trigram_jaccard("queen street", "") == pytest.approx(0.0)

    def test_symmetric(self) -> None:
        """Jaccard similarity is symmetric."""
        a, b = "victoria street west", "victoria street"
        assert _trigram_jaccard(a, b) == pytest.approx(_trigram_jaccard(b, a))


class TestPickCity:
    """Tests for the _pick_city helper."""

    def test_first_non_empty(self) -> None:
        """First non-empty column is returned."""
        assert _pick_city("Auckland", "Wellington") == "Auckland"

    def test_fallback_to_second(self) -> None:
        """Falls back to second column when first is empty."""
        assert _pick_city("", "Wellington") == "Wellington"

    def test_both_empty(self) -> None:
        """Returns empty string when both are empty."""
        assert _pick_city("", "") == ""

    def test_trims_whitespace(self) -> None:
        """Whitespace-only strings are treated as empty."""
        assert _pick_city("  ", "Auckland") == "Auckland"


class TestNormalizeDataFrame:
    """Tests for the normalize DataFrame function."""

    def test_adds_normalised_columns(self) -> None:
        """Normalised columns are created for street, suburb, city."""
        df = pd.DataFrame(
            {
                "street": ["16 Amritsar Street"],
                "suburb": ["Sandringham"],
                "city": ["Auckland"],
            },
        )
        result = normalize(df)
        assert "street_norm" in result.columns
        assert "suburb_norm" in result.columns
        assert "city_norm" in result.columns
        assert result["street_norm"].iloc[0] == "16 amritsar street"
        assert result["city_norm"].iloc[0] == "auckland"

    def test_adds_street_number_and_name(self) -> None:
        """Street number and name are split into separate columns."""
        df = pd.DataFrame({"street": ["16 Amritsar Street"]})
        result = normalize(df)
        assert result["street_number_norm"].iloc[0] == "16"
        assert result["street_name_norm"].iloc[0] == "amritsar street"

    def test_no_street_column(self) -> None:
        """No error when street column is missing."""
        df = pd.DataFrame({"city": ["Auckland"]})
        result = normalize(df)
        assert "street_number_norm" not in result.columns
        assert "city_norm" in result.columns

    def test_original_columns_preserved(self) -> None:
        """Original unnormalised columns remain unchanged."""
        df = pd.DataFrame({"street": ["Queen Street"], "city": ["Auckland"]})
        result = normalize(df)
        assert result["street"].iloc[0] == "Queen Street"


class TestExtractAddressesFromCsv:
    """Tests for extract_addresses_from_csv with temp CSV files."""

    def test_shareholder_addresses(self, tmp_path: pytest.TempPathFactory) -> None:
        """Extracts and deduplicates shareholder addresses."""
        csv_path = tmp_path / "companies_shareholder.csv"
        csv_path.write_text(
            "SH_ADDRESS_1,SH_ADDRESS_2,SH_ADDRESS_3,SH_ADDRESS_4,SH_ADDRESS_POSTCODE,SH_ADDRESS_COUNTRY\n"
            "16 Amritsar St,Sandringham,Auckland,,1025,New Zealand\n"
            "10 Queen St,City,Auckland,,1010,New Zealand\n",
        )
        df = extract_addresses_from_csv(tmp_path)
        assert len(df) == 2  # noqa: PLR2004
        assert "id" in df.columns
        assert df["street"].iloc[0] == "16 Amritsar St"
        assert df["city"].iloc[0] == "Auckland"

    def test_deduplicates_across_sources(self, tmp_path: pytest.TempPathFactory) -> None:
        """Same address from different sources is deduplicated."""
        (tmp_path / "companies_shareholder.csv").write_text(
            "SH_ADDRESS_1,SH_ADDRESS_2,SH_ADDRESS_3,SH_ADDRESS_4,SH_ADDRESS_POSTCODE,SH_ADDRESS_COUNTRY\n"
            "16 Amritsar St,Sandringham,Auckland,,1025,New Zealand\n",
        )
        (tmp_path / "companies_public_address.csv").write_text(
            "ADDRESS_1,ADDRESS_2,ADDRESS_3,ADDRESS_4,ADDRESS_POSTCODE,ADDRESS_COUNTRY,TYPE,START_DATE\n"
            "16 Amritsar St,Sandringham,Auckland,,1025,New Zealand,Registered Office,2020-01-01\n",
        )
        df = extract_addresses_from_csv(tmp_path)
        assert len(df) == 1

    def test_filters_non_nz(self, tmp_path: pytest.TempPathFactory) -> None:
        """Non-NZ addresses are filtered out."""
        (tmp_path / "companies_shareholder.csv").write_text(
            "SH_ADDRESS_1,SH_ADDRESS_2,SH_ADDRESS_3,SH_ADDRESS_4,SH_ADDRESS_POSTCODE,SH_ADDRESS_COUNTRY\n"
            "16 Amritsar St,Sandringham,Auckland,,1025,New Zealand\n"
            "10 Wall St,,New York,,10005,United States\n",
        )
        df = extract_addresses_from_csv(tmp_path)
        assert len(df) == 1
        assert df["city"].iloc[0] == "Auckland"

    def test_empty_country_included(self, tmp_path: pytest.TempPathFactory) -> None:
        """Empty country is kept (likely NZ)."""
        (tmp_path / "companies_shareholder.csv").write_text(
            "SH_ADDRESS_1,SH_ADDRESS_2,SH_ADDRESS_3,SH_ADDRESS_4,SH_ADDRESS_POSTCODE,SH_ADDRESS_COUNTRY\n"
            "16 Amritsar St,Sandringham,Auckland,,1025,\n",
        )
        df = extract_addresses_from_csv(tmp_path)
        assert len(df) == 1

    def test_city_column_fallback(self, tmp_path: pytest.TempPathFactory) -> None:
        """Falls back to SH_ADDRESS_4 when SH_ADDRESS_3 is empty."""
        (tmp_path / "companies_shareholder.csv").write_text(
            "SH_ADDRESS_1,SH_ADDRESS_2,SH_ADDRESS_3,SH_ADDRESS_4,SH_ADDRESS_POSTCODE,SH_ADDRESS_COUNTRY\n"
            "16 Amritsar St,Sandringham,,Auckland City,1025,New Zealand\n",
        )
        df = extract_addresses_from_csv(tmp_path)
        assert df["city"].iloc[0] == "Auckland City"

    def test_raises_on_missing_dir(self, tmp_path: pytest.TempPathFactory) -> None:
        """Raises FileNotFoundError when no CSV files exist."""
        with pytest.raises(FileNotFoundError):
            extract_addresses_from_csv(tmp_path)


class TestStageExact:
    """Tests for the exact matching stage."""

    def test_exact_city_number_street_match(self) -> None:
        """Exact match on city, number, and street name returns coordinates."""
        neo = pd.DataFrame(
            {
                "id": [1],
                "city_norm": ["auckland"],
                "street_number_norm": ["16"],
                "street_name_norm": ["amritsar street"],
            },
        )
        linz = pd.DataFrame(
            {
                "city_norm": ["auckland"],
                "street_number_norm": ["16"],
                "street_name_norm": ["amritsar street"],
                "lat": [-36.87],
                "lng": [174.74],
            },
        )
        matched, unmatched = _stage_exact(neo, linz)
        assert len(matched) == 1
        assert matched["lat"].iloc[0] == -36.87  # noqa: PLR2004
        assert len(unmatched) == 0

    def test_no_match_returns_empty_matched(self) -> None:
        """No match returns empty matched and full unmatched."""
        neo = pd.DataFrame(
            {
                "id": [1],
                "city_norm": ["auckland"],
                "street_number_norm": ["16"],
                "street_name_norm": ["amritsar street"],
            },
        )
        linz = pd.DataFrame(
            {
                "city_norm": ["wellington"],
                "street_number_norm": ["10"],
                "street_name_norm": ["queen street"],
                "lat": [-41.29],
                "lng": [174.78],
            },
        )
        matched, unmatched = _stage_exact(neo, linz)
        assert len(matched) == 0
        assert len(unmatched) == 1

    def test_partial_city_match_not_exact(self) -> None:
        """Missing street number prevents exact match even with same city+name."""
        neo = pd.DataFrame(
            {
                "id": [1],
                "city_norm": ["auckland"],
                "street_number_norm": [""],
                "street_name_norm": ["queen street"],
            },
        )
        linz = pd.DataFrame(
            {
                "city_norm": ["auckland"],
                "street_number_norm": ["10"],
                "street_name_norm": ["queen street"],
                "lat": [-36.84],
                "lng": [174.76],
            },
        )
        matched, unmatched = _stage_exact(neo, linz)
        assert len(matched) == 0
        assert len(unmatched) == 1


class TestStageNameFallback:
    """Tests for the name-fallback matching stage."""

    def test_match_on_city_and_street_name(self) -> None:
        """Match succeeds on city + street name alone."""
        neo = pd.DataFrame(
            {
                "id": [1],
                "city_norm": ["auckland"],
                "street_name_norm": ["queen street"],
            },
        )
        linz = pd.DataFrame(
            {
                "city_norm": ["auckland"],
                "street_name_norm": ["queen street"],
                "lat": [-36.84],
                "lng": [174.76],
            },
        )
        matched, _ = _stage_name_fallback(neo, linz)
        assert len(matched) == 1
        assert matched.iloc[0]["match_stage"] == "name_fallback"
        assert matched.iloc[0]["match_confidence"] == "high"

    def test_different_city_no_match(self) -> None:
        """Different city prevents match even with same street name."""
        neo = pd.DataFrame(
            {
                "id": [1],
                "city_norm": ["auckland"],
                "street_name_norm": ["queen street"],
            },
        )
        linz = pd.DataFrame(
            {
                "city_norm": ["wellington"],
                "street_name_norm": ["queen street"],
                "lat": [-41.29],
                "lng": [174.78],
            },
        )
        matched, remaining = _stage_name_fallback(neo, linz)
        assert len(matched) == 0
        assert len(remaining) == 1


class TestScoreCandidates:
    """Tests for the _score_candidates helper."""

    def test_exact_match(self) -> None:
        """Same city + identical trigrams returns the entry."""
        trigrams = _trigrams("queen street")
        entry_dict = {
            0: {"lat": -41.29, "lng": 174.78, "trigrams": trigrams, "city_norm": "wellington"},
        }
        result, _ = _score_candidates(trigrams, [0], entry_dict, city="wellington", threshold=0.5)
        assert result is not None
        assert result["lat"] == -41.29  # noqa: PLR2004

    def test_city_filter_excludes(self) -> None:
        """Different city returns None even if trigrams match."""
        trigrams = _trigrams("queen street")
        entry_dict = {
            0: {"lat": -41.29, "lng": 174.78, "trigrams": trigrams, "city_norm": "auckland"},
        }
        result, score = _score_candidates(trigrams, [0], entry_dict, city="wellington", threshold=0.5)
        assert result is None
        assert score == 0.0

    def test_below_threshold(self) -> None:
        """Very different street name scores below threshold."""
        q = _trigrams("queen street")
        d = _trigrams("industrial road")
        entry_dict = {
            0: {"lat": 0.0, "lng": 0.0, "trigrams": d, "city_norm": "wellington"},
        }
        result, score = _score_candidates(q, [0], entry_dict, city="wellington", threshold=0.9)
        assert result is None
        assert score < 0.5  # noqa: PLR2004

    def test_empty_candidates(self) -> None:
        """Empty candidate list returns None."""
        trigrams = _trigrams("queen street")
        result, score = _score_candidates(trigrams, [], {}, city="wellington")
        assert result is None
        assert score == 0.0


class TestBuildLshIndex:
    """Tests for the _build_lsh_index function."""

    def test_build_and_query(self) -> None:
        """Index is built and query finds similar entries."""
        linz = pd.DataFrame(
            {
                "town_city": ["Wellington"],
                "road_name": ["Queens Drive"],
                "lat": [-41.29],
                "lng": [174.78],
                "city_norm": ["wellington"],
                "street_number_norm": [""],
                "street_name_norm": ["queens drive"],
            },
        )
        lsh, entries = _build_lsh_index(linz, num_perm=128, threshold=0.3)

        row = {"id": 0, "city_norm": "wellington", "street_name_norm": "queen drive"}
        result = _lsh_match_row(row, lsh, entries, threshold=0.5)
        assert result is not None
        assert result["lat"] == -41.29  # noqa: PLR2004
        assert result["lng"] == 174.78  # noqa: PLR2004
        assert result["match_stage"] == "fuzzy"

    def test_no_match_for_different_street(self) -> None:
        """Unrelated street name returns None."""
        linz = pd.DataFrame(
            {
                "town_city": ["Wellington"],
                "road_name": ["Queens Drive"],
                "lat": [-41.29],
                "lng": [174.78],
                "city_norm": ["wellington"],
                "street_number_norm": [""],
                "street_name_norm": ["queens drive"],
            },
        )
        lsh, entries = _build_lsh_index(linz, num_perm=128, threshold=0.3)

        row = {"id": 0, "city_norm": "wellington", "street_name_norm": "industrial road"}
        result = _lsh_match_row(row, lsh, entries, threshold=0.5)
        assert result is None

    def test_matches_correct_city(self) -> None:
        """Only same-city entries are matched, even if LSH returns cross-city."""
        linz = pd.DataFrame(
            {
                "town_city": ["Wellington", "Auckland"],
                "road_name": ["Queens Drive", "Queen Street"],
                "lat": [-41.29, -36.85],
                "lng": [174.78, 174.76],
                "city_norm": ["wellington", "auckland"],
                "street_number_norm": ["", ""],
                "street_name_norm": ["queens drive", "queens drive"],
            },
        )
        lsh, entries = _build_lsh_index(linz, num_perm=128, threshold=0.3)

        row = {"id": 0, "city_norm": "wellington", "street_name_norm": "queen drive"}
        result = _lsh_match_row(row, lsh, entries, threshold=0.5)
        assert result is not None
        assert result["lat"] == -41.29  # noqa: PLR2004  # Wellington, not Auckland
