"""Reverse geocode addresses using the LINZ NZ Addresses dataset.

Extracts unique addresses from raw CSV files, matches them against the
LINZ shapefile using multi-stage matching, and writes the result CSV for
later consumption (e.g. an enrichment step persists coordinates to Neo4j).
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

import pandas as pd
import shapefile
from datasketch import MinHash
from datasketch import MinHashLSH

from nz_companies_office.config import SETTINGS

logger = logging.getLogger(__name__)

ABBREVIATIONS = {
    "st": "street",
    "rd": "road",
    "ave": "avenue",
    "dr": "drive",
    "ln": "lane",
    "ct": "court",
    "pl": "place",
    "tce": "terrace",
    "hwy": "highway",
    "cres": "crescent",
    "gr": "grove",
    "cl": "close",
    "bvd": "boulevard",
    "pde": "parade",
}

MACRON_MAP = str.maketrans(
    {
        "ā": "a",
        "ē": "e",
        "ī": "i",
        "ō": "o",
        "ū": "u",
        "Ā": "A",
        "Ē": "E",
        "Ī": "I",
        "Ō": "O",
        "Ū": "U",
    },
)

DEFAULT_DATA_DIR = SETTINGS.raw_data_dir
DEFAULT_EXPORT_PATH = SETTINGS.geocode_export_path
DEFAULT_RESULT_PATH = SETTINGS.geocode_result_path

ADDR_COLS = ["street", "suburb", "city"]

CSV_FILES = {
    "shareholder": "companies_shareholder.csv",
    "registered_office": "companies_registered_office_address.csv",
    "service": "companies_address_for_service.csv",
    "public": "companies_public_address.csv",
}

_ADDRESS_COLUMNS: dict[str, dict[str, str]] = {
    "shareholder": {
        "street": "SH_ADDRESS_1",
        "suburb": "SH_ADDRESS_2",
        "postcode": "SH_ADDRESS_POSTCODE",
        "country": "SH_ADDRESS_COUNTRY",
    },
    "registered_office": {
        "street": "REGISTERED_OFFICE_ADDRESS_1",
        "suburb": "REGISTERED_OFFICE_ADDRESS_2",
        "postcode": "REGISTERED_OFFICE_ADDRESS_POSTCODE",
        "country": "REGISTERED_OFFICE_ADDRESS_COUNTRY",
    },
    "service": {
        "street": "ADDRESS_FOR_SERVICE_1",
        "suburb": "ADDRESS_FOR_SERVICE_2",
        "postcode": "ADDRESS_FOR_SERVICE_POSTCODE",
        "country": "ADDRESS_FOR_SERVICE_COUNTRY",
    },
    "public": {
        "street": "ADDRESS_1",
        "suburb": "ADDRESS_2",
        "postcode": "ADDRESS_POSTCODE",
        "country": "ADDRESS_COUNTRY",
    },
}

_CITY_COLUMN_PAIRS: dict[str, tuple[str, str]] = {
    "shareholder": ("SH_ADDRESS_3", "SH_ADDRESS_4"),
    "registered_office": ("REGISTERED_OFFICE_ADDRESS_3", "REGISTERED_OFFICE_ADDRESS_4"),
    "service": ("ADDRESS_FOR_SERVICE_3", "ADDRESS_FOR_SERVICE_4"),
    "public": ("ADDRESS_3", "ADDRESS_4"),
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _normalize_text(text: str | None) -> str:
    if text is None:
        return ""
    s = text.lower().strip()
    s = s.translate(MACRON_MAP)
    s = "".join(c for c in s if c.isalnum() or c in " -'")
    s = " ".join(s.split())
    parts = s.split()
    parts = [ABBREVIATIONS.get(p, p) for p in parts]
    return " ".join(parts)


def _parse_street_number(street: str | None) -> tuple[str, str]:
    if not street:
        return ("", "")
    s = street.strip()
    parts = s.split(" ", 1)
    if len(parts) == 1:
        return ("", s.lower())
    first, rest = parts
    if first.isdigit() or (first[:-1].isdigit() and not first[-1].isalpha()):
        return (first, rest.lower())
    if any(c.isdigit() for c in first):
        return (first, rest.lower())
    return ("", s.lower())


def _trigrams(s: str) -> frozenset[str]:
    """Compute the trigram set for a string."""
    padded = "  " + s.lower() + " "
    return frozenset(padded[i : i + 3] for i in range(len(padded) - 2))


def _trigram_jaccard(a: str, b: str) -> float:
    if not a or not b:
        return 0.0
    a_tri = _trigrams(a)
    b_tri = _trigrams(b)
    inter = len(a_tri & b_tri)
    union = len(a_tri | b_tri)
    return inter / union if union > 0 else 0.0


def _pick_city(col3: str, col4: str) -> str:
    c3 = col3.strip()
    c4 = col4.strip()
    return c3 or c4


# ---------------------------------------------------------------------------
# ETL: extract addresses from raw CSV
# ---------------------------------------------------------------------------


def _csv_exists(path: Path) -> bool:
    """Return True if the path exists, swallowing permission/OS errors."""
    try:
        return path.exists()
    except OSError:
        return False


def _resolve_csv_dir(data_dir: Path) -> Path:
    """Resolve the directory that actually contains the address CSVs.

    The default ``raw_data_dir`` (``data/raw``) holds dated export
    subdirectories (e.g. ``202607/``) rather than the CSVs directly. If no
    address CSV is found in ``data_dir`` itself, pick the most recent dated
    subdirectory (sorted by name, treating ``YYYYMM`` as descending).
    """

    def _has_csvs(directory: Path) -> bool:
        return any(_csv_exists(directory / CSV_FILES[s]) for s in CSV_FILES)

    data_dir = Path(data_dir)
    if _has_csvs(data_dir):
        return data_dir

    dated = sorted(
        (p for p in data_dir.iterdir() if p.is_dir() and _has_csvs(p)),
        key=lambda p: p.name,
        reverse=True,
    )
    if dated:
        logger.info("No address CSVs in %s; using export dir %s", data_dir, dated[0])
        return dated[0]

    return data_dir


def extract_addresses_from_csv(data_dir: Path) -> pd.DataFrame:
    """Extract unique NZ addresses from raw CSV files.

    Reads all 4 address-bearing CSV files, normalises columns to a common
    schema, filters to NZ-only, and deduplicates.  When ``data_dir`` does not
    directly contain the CSVs, the most recent dated export subdirectory is
    used automatically.
    """
    data_dir = _resolve_csv_dir(data_dir)
    all_frames: list[pd.DataFrame] = []

    for source in ("shareholder", "registered_office", "service", "public"):
        path = data_dir / CSV_FILES[source]
        if not path.exists():
            logger.warning("Skipping %s: %s not found", source, path)
            continue

        cols = _ADDRESS_COLUMNS[source]
        city_cols = _CITY_COLUMN_PAIRS[source]
        df = pd.read_csv(
            path,
            usecols=[cols["street"], cols["suburb"], city_cols[0], city_cols[1], cols["postcode"], cols["country"]],
            dtype=str,
        ).fillna("")

        col3 = df[city_cols[0]].str.strip()
        col4 = df[city_cols[1]].str.strip()
        city = col3.where(col3 != "", col4)

        result = pd.DataFrame(
            {
                "street": df[cols["street"]],
                "suburb": df[cols["suburb"]],
                "city": city,
                "postcode": df[cols["postcode"]],
                "country": df[cols["country"]],
            },
        )
        all_frames.append(result)

    if not all_frames:
        msg = f"No address CSV files found in {data_dir}"
        raise FileNotFoundError(msg)

    combined = pd.concat(all_frames, ignore_index=True)

    nz_mask = combined["country"].str.lower().str.contains("new zealand", na=False) | (combined["country"] == "")
    combined = combined[nz_mask].copy()

    key_cols = ["street", "suburb", "city", "postcode", "country"]
    combined = combined.drop_duplicates(subset=key_cols).reset_index(drop=True)
    combined["id"] = combined.index

    logger.info("Extracted %d unique NZ addresses from raw CSV", len(combined))
    return combined


# ---------------------------------------------------------------------------
# Matching helpers
# ---------------------------------------------------------------------------


def normalize(df: pd.DataFrame) -> pd.DataFrame:
    """Add normalised columns for street, suburb, city."""
    df = df.copy()
    for col in ADDR_COLS:
        if col in df.columns:
            df[f"{col}_norm"] = df[col].apply(_normalize_text)
    if "street" in df.columns:
        num_name = df["street"].apply(_parse_street_number)
        df["street_number_norm"] = [x[0] for x in num_name]
        df["street_name_norm"] = [x[1] for x in num_name]
    return df


# ---------------------------------------------------------------------------
# LINZ loading + caching (raw and normalized)
# ---------------------------------------------------------------------------

_LINZ_RAW_COLS = ["town_city", "road_name", "lat", "lng"]


def _load_linz_shapefile(shp_path: Path) -> pd.DataFrame:
    """Load only the needed columns from the LINZ shapefile."""
    sf = shapefile.Reader(str(shp_path))
    fields = [f[0] for f in sf.fields[1:]]
    records: list[dict] = []
    for rec, shp in zip(sf.iterRecords(), sf.iterShapes(), strict=True):
        rec_dict = dict(zip(fields, rec, strict=True))
        rec_dict["lat"] = shp.points[0][1]
        rec_dict["lng"] = shp.points[0][0]
        records.append({k: rec_dict[k] for k in _LINZ_RAW_COLS if k in rec_dict})
    return pd.DataFrame(records)


def prepare_linz_cache(
    shp_path: Path | None = None,
    cache_path: Path | None = None,
) -> Path:
    """Transform the LINZ shapefile into a cached CSV (only needed columns).

    Removes any stale normalized cache so both caches stay in sync.
    Returns the path to the cache file.
    """
    src = shp_path or SETTINGS.linz_shp_path
    dst = cache_path or SETTINGS.linz_cache_path
    if dst.exists():
        logger.info("LINZ cache already exists at %s", dst)
        return dst
    norm_dst = _norm_cache_path(dst)
    norm_dst.unlink(missing_ok=True)
    t0 = time.perf_counter()
    dst.parent.mkdir(parents=True, exist_ok=True)
    df = _load_linz_shapefile(src)
    df.to_parquet(dst, index=False)
    elapsed = time.perf_counter() - t0
    logger.info("Wrote %d LINZ addresses to cache %s (%.2f s)", len(df), dst, elapsed)
    return dst


def _norm_cache_path(raw_cache: Path) -> Path:
    return raw_cache.with_stem(raw_cache.stem + "-norm")


def load_linz_addresses(
    shp_path: Path | None = None,
    cache_path: Path | None = None,
) -> pd.DataFrame:
    """Load raw LINZ NZ Addresses from shapefile or parquet cache (slim columns only)."""
    cache = cache_path or SETTINGS.linz_cache_path
    if cache.exists():
        t0 = time.perf_counter()
        df = pd.read_parquet(cache)
        elapsed = time.perf_counter() - t0
        logger.info("Loaded %d LINZ addresses from cache (%.2f s)", len(df), elapsed)
        return df
    src = shp_path or SETTINGS.linz_shp_path
    t0 = time.perf_counter()
    df = _load_linz_shapefile(src)
    cache.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(cache, index=False)
    elapsed = time.perf_counter() - t0
    logger.info("Loaded %d LINZ addresses from shapefile and cached (%.2f s)", len(df), elapsed)
    return df


def load_linz_norm(
    shp_path: Path | None = None,
    cache_path: Path | None = None,
) -> pd.DataFrame:
    """Load or build normalized LINZ addresses with precomputed columns.

    Returns a DataFrame with raw columns + ``city_norm``,
    ``street_number_norm``, ``street_name_norm``.  The normalized result is
    cached on disk so subsequent runs skip normalization entirely.
    """
    cache = cache_path or SETTINGS.linz_cache_path
    norm_cache = _norm_cache_path(cache)

    if norm_cache.exists():
        t0 = time.perf_counter()
        df = pd.read_parquet(norm_cache)
        elapsed = time.perf_counter() - t0
        logger.info("Loaded %d normalized LINZ addresses from cache (%.2f s)", len(df), elapsed)
        return df

    raw = load_linz_addresses(shp_path, cache)
    t0 = time.perf_counter()
    raw["city_norm"] = raw["town_city"].apply(_normalize_text)
    road_parts = raw["road_name"].apply(_parse_street_number)
    raw["street_number_norm"] = [x[0] for x in road_parts]
    raw["street_name_norm"] = [x[1] for x in road_parts]
    norm_cache.parent.mkdir(parents=True, exist_ok=True)
    raw.to_parquet(norm_cache, index=False)
    elapsed = time.perf_counter() - t0
    logger.info("Normalized %d LINZ addresses and cached (%.2f s)", len(raw), elapsed)
    return raw


# ---------------------------------------------------------------------------
# LSH index builder
# ---------------------------------------------------------------------------


@dataclass
class LshIndex:
    """Container for a built MinHash LSH index and its lookup table."""

    index: MinHashLSH
    entries: dict[int, dict]


def _build_lsh_index(
    linz_norm: pd.DataFrame,
    *,
    num_perm: int = SETTINGS.geocode_lsh_num_perm,
    threshold: float = SETTINGS.geocode_lsh_threshold,
) -> tuple[MinHashLSH, dict[int, dict]]:
    """Build a MinHash LSH index over LINZ street names.

    Returns:
    -------
    tuple[MinHashLSH, dict[int, dict]]
        The LSH index and a lookup dict mapping integer key to
        ``{"lat", "lng", "trigrams", "city_norm"}``.
    """
    lsh = MinHashLSH(threshold=threshold, num_perm=num_perm)
    entries: dict[int, dict] = {}

    for row in linz_norm.itertuples():
        key = int(row.Index)
        street_name = str(row.street_name_norm) if hasattr(row, "street_name_norm") else ""
        tri_set = _trigrams(street_name)
        mh = MinHash(num_perm=num_perm)
        for tri in tri_set:
            mh.update(tri.encode("utf8"))
        lsh.insert(key, mh)
        entries[key] = {
            "lat": row.lat,
            "lng": row.lng,
            "trigrams": tri_set,
            "city_norm": str(row.city_norm) if hasattr(row, "city_norm") else "",
        }

    return lsh, entries


# ---------------------------------------------------------------------------
# Matching strategies (Strategy pattern)
# ---------------------------------------------------------------------------


class Matcher(Protocol):
    """Strategy contract for a single matching stage.

    Each matcher consumes the still-unmatched source rows and returns the
    rows it matched (annotated with ``match_stage`` / ``match_confidence``)
    together with the rows that remain unmatched.
    """

    stage_name: str

    def match(
        self,
        source_df: pd.DataFrame,
        linz_norm: pd.DataFrame,
        lsh_index: LshIndex | None = None,
    ) -> tuple[pd.DataFrame, pd.DataFrame]:
        """Match a subset of addresses, returning (matched, remaining)."""
        ...


def _merge_coords(unmatched: pd.DataFrame, linz_norm: pd.DataFrame, key_cols: list[str]) -> pd.DataFrame:
    """Inner-join unmatched rows to LINZ by a computed match key."""
    match = unmatched.copy()
    match["match_key"] = match[key_cols].fillna("").agg(":".join, axis=1)
    linz_key = linz_norm[key_cols].fillna("").agg(":".join, axis=1)
    merged = match.merge(
        pd.DataFrame({"match_key": linz_key, "lat": linz_norm["lat"], "lng": linz_norm["lng"]}),
        on="match_key",
        how="inner",
    )
    return merged.drop_duplicates(subset="id")


class ExactMatcher:
    """Match on city + street number + street name exactly."""

    stage_name = "exact"

    def match(
        self,
        source_df: pd.DataFrame,
        linz_norm: pd.DataFrame,
        lsh_index: LshIndex | None = None,  # noqa: ARG002
    ) -> tuple[pd.DataFrame, pd.DataFrame]:
        """Match on city + street number + street name exactly."""
        key_cols = ["city_norm", "street_number_norm", "street_name_norm"]
        merged = _merge_coords(source_df, linz_norm, key_cols)
        merged["match_stage"] = self.stage_name
        merged["match_confidence"] = "exact"

        matched_ids = set(merged["id"])
        unmatched = source_df[~source_df["id"].isin(matched_ids)].copy()
        return merged, unmatched


class NameFallbackMatcher:
    """Match on city + street name alone (ignoring street number)."""

    stage_name = "name_fallback"

    def match(
        self,
        source_df: pd.DataFrame,
        linz_norm: pd.DataFrame,
        lsh_index: LshIndex | None = None,  # noqa: ARG002
    ) -> tuple[pd.DataFrame, pd.DataFrame]:
        """Match on city + street name alone (ignoring street number)."""
        key_cols = ["city_norm", "street_name_norm"]
        merged = _merge_coords(source_df, linz_norm, key_cols)
        merged["match_stage"] = self.stage_name
        merged["match_confidence"] = "high"

        matched_ids = set(merged["id"])
        remaining = source_df[~source_df["id"].isin(matched_ids)].copy()
        return merged, remaining


def _score_candidates(
    input_trigrams: frozenset[str],
    candidate_keys: list[int],
    entry_dict: dict[int, dict],
    *,
    city: str,
    threshold: float = SETTINGS.geocode_trigram_min_score,
) -> tuple[dict | None, float]:
    """Score candidates by exact trigram Jaccard, filtered by city.

    Returns (best_entry, best_score).
    """
    best_score = 0.0
    best = None
    for key in candidate_keys:
        c = entry_dict[key]
        if c["city_norm"] != city:
            continue
        inter = len(input_trigrams & c["trigrams"])
        union = len(input_trigrams | c["trigrams"])
        score = inter / union if union > 0 else 0.0
        if score > best_score:
            best_score = score
            best = c
    if best is not None and best_score >= threshold:
        return best, best_score
    return None, best_score


def _lsh_match_row(
    row: dict,
    lsh: MinHashLSH,
    entry_dict: dict[int, dict],
    *,
    threshold: float = SETTINGS.geocode_trigram_min_score,
) -> dict | None:
    """Match a single address row against the LSH index.

    Returns a result dict with ``id``, ``lat``, ``lng``, ``match_stage``,
    ``match_confidence``, or ``None`` if no match found.
    """
    addr_id = row["id"]
    city = str(row.get("city_norm", ""))
    street_name = str(row.get("street_name_norm", ""))
    if not street_name:
        return None

    input_trigrams = _trigrams(street_name)
    q_mh = MinHash(num_perm=SETTINGS.geocode_lsh_num_perm)
    for tri in input_trigrams:
        q_mh.update(tri.encode("utf8"))

    candidate_keys = lsh.query(q_mh)
    if not candidate_keys:
        return None

    best, best_score = _score_candidates(input_trigrams, candidate_keys, entry_dict, city=city, threshold=threshold)
    if best is None:
        return None

    return {
        "id": addr_id,
        "lat": best["lat"],
        "lng": best["lng"],
        "match_stage": "fuzzy",
        "match_confidence": "high" if best_score >= SETTINGS.geocode_trigram_high_confidence else "medium",
    }


class FuzzyMatcher:
    """Match remaining addresses using MinHash LSH + city-filtered Jaccard."""

    stage_name = "fuzzy"

    def match(
        self,
        source_df: pd.DataFrame,
        linz_norm: pd.DataFrame,  # noqa: ARG002
        lsh_index: LshIndex | None = None,
    ) -> tuple[pd.DataFrame, pd.DataFrame]:
        """Match addresses using MinHash LSH + city-filtered Jaccard."""
        if lsh_index is None:
            msg = "FuzzyMatcher requires an LshIndex"
            raise ValueError(msg)
        t0 = time.perf_counter()

        rows = source_df.to_dict(orient="records")
        all_results: list[dict] = []
        all_remaining: list[int] = []

        for row in rows:
            result = _lsh_match_row(
                row,
                lsh_index.index,
                lsh_index.entries,
                threshold=SETTINGS.geocode_trigram_min_score,
            )
            if result is not None:
                all_results.append(result)
            else:
                all_remaining.append(row["id"])

        still_unmatched = source_df[source_df["id"].isin(all_remaining)].copy()
        if all_results:
            result_df = pd.DataFrame(all_results)
            fuzzy_matched = still_unmatched.merge(result_df, on="id", how="right", suffixes=("_drop", ""))
            drop_cols = [c for c in fuzzy_matched.columns if c.endswith("_drop")]
            fuzzy_matched = fuzzy_matched.drop(columns=drop_cols)
        else:
            fuzzy_matched = pd.DataFrame()

        elapsed = time.perf_counter() - t0
        logger.info("Stage (fuzzy LSH): %d matched (%.2f s)", len(fuzzy_matched), elapsed)
        return fuzzy_matched, still_unmatched


# ---------------------------------------------------------------------------
# Backward-compatible module-level wrappers (delegate to strategies)
# ---------------------------------------------------------------------------


def _stage_exact(source_df: pd.DataFrame, linz_norm: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Deprecated: use :class:`ExactMatcher` via :class:`Geocoder`."""
    return ExactMatcher().match(source_df, linz_norm)


def _stage_name_fallback(unmatched: pd.DataFrame, linz_norm: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Deprecated: use :class:`NameFallbackMatcher` via :class:`Geocoder`."""
    return NameFallbackMatcher().match(unmatched, linz_norm)


def _stage_fuzzy(
    unmatched: pd.DataFrame,
    lsh: MinHashLSH,
    entry_dict: dict[int, dict],
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Deprecated: use :class:`FuzzyMatcher` via :class:`Geocoder`."""
    lsh_index = LshIndex(index=lsh, entries=entry_dict)
    return FuzzyMatcher().match(unmatched, pd.DataFrame(), lsh_index)


# ---------------------------------------------------------------------------
# Pipeline orchestration
# ---------------------------------------------------------------------------


class Geocoder:
    """Orchestrates the multi-stage reverse-geocoding pipeline.

    Encapsulates normalisation, LSH index construction, the ordered set of
    matching strategies, and the final unmatched labelling.
    """

    def __init__(
        self,
        *,
        matchers: list[Matcher] | None = None,
        trigram_min_score: float = SETTINGS.geocode_trigram_min_score,
        trigram_high_confidence: float = SETTINGS.geocode_trigram_high_confidence,
        lsh_num_perm: int = SETTINGS.geocode_lsh_num_perm,
        lsh_threshold: float = SETTINGS.geocode_lsh_threshold,
    ) -> None:
        """Initialise the pipeline with its matching strategies.

        Args:
            matchers: Ordered list of matching strategies. Defaults to
                exact → name-fallback → fuzzy.
            trigram_min_score: Minimum Jaccard score for a fuzzy match.
            trigram_high_confidence: Score above which fuzzy matches are "high".
            lsh_num_perm: Number of permutations for the MinHash LSH index.
            lsh_threshold: LSH banding threshold.

        """
        self._matchers = matchers or [ExactMatcher(), NameFallbackMatcher(), FuzzyMatcher()]
        self._trigram_min_score = trigram_min_score
        self._trigram_high_confidence = trigram_high_confidence
        self._lsh_num_perm = lsh_num_perm
        self._lsh_threshold = lsh_threshold

    def match(self, source_df: pd.DataFrame, linz_norm: pd.DataFrame) -> pd.DataFrame:
        """Run the multi-stage address matching pipeline.

        Args:
            source_df: Raw source addresses (normalised internally).
            linz_norm: Pre-normalised LINZ addresses via
                :func:`load_linz_norm`.

        Returns:
            DataFrame of all addresses annotated with ``lat``, ``lng``,
            ``match_stage`` and ``match_confidence`` columns.

        """
        t0 = time.perf_counter()

        source_norm = normalize(source_df)
        lsh, linz_entries = _build_lsh_index(
            linz_norm,
            num_perm=self._lsh_num_perm,
            threshold=self._lsh_threshold,
        )
        lsh_index = LshIndex(index=lsh, entries=linz_entries)

        matched_frames: list[pd.DataFrame] = []
        remaining = source_norm
        for matcher in self._matchers:
            if isinstance(matcher, FuzzyMatcher):
                matched, remaining = matcher.match(remaining, linz_norm, lsh_index)
            else:
                matched, remaining = matcher.match(remaining, linz_norm)
            matched_frames.append(matched)
            logger.info("Stage (%s): %d matched", matcher.stage_name, len(matched))

        all_matched_ids = set()
        for df in matched_frames:
            if not df.empty:
                all_matched_ids.update(df["id"])
        if all_matched_ids:
            remaining = remaining[~remaining["id"].isin(all_matched_ids)]

        for col in ("lat", "lng", "match_stage", "match_confidence"):
            remaining[col] = None
        remaining["match_stage"] = "unmatched"
        remaining["match_confidence"] = "none"

        result = pd.concat([*matched_frames, remaining], ignore_index=True)
        elapsed = time.perf_counter() - t0

        matched = result[result["match_stage"] != "unmatched"]
        logger.info(
            "Matching complete: %d / %d matched (%.1f%%) in %.2f s",
            len(matched),
            len(result),
            len(matched) / len(result) * 100 if len(result) > 0 else 0,
            elapsed,
        )

        out_cols = [
            "id",
            "street",
            "suburb",
            "city",
            "postcode",
            "country",
            "lat",
            "lng",
            "match_stage",
            "match_confidence",
        ]
        return result[[c for c in out_cols if c in result.columns]]


def match_addresses(
    source_df: pd.DataFrame,
    linz_norm: pd.DataFrame,
) -> pd.DataFrame:
    """Run multi-stage address matching pipeline.

    Parameters
    ----------
    source_df:
        Raw source addresses (will be normalised internally).
    linz_norm:
        Pre-normalised LINZ addresses via :func:`load_linz_norm`.
    """
    return Geocoder().match(source_df, linz_norm)


def write_csv(matches: pd.DataFrame, output_path: Path) -> None:
    """Write matched addresses to CSV for review."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    matches.to_csv(output_path, index=False)
    logger.info("Wrote %d rows to %s", len(matches), output_path)


def geocode(
    *,
    export_path: Path | None = None,
    result_path: Path | None = None,
    shp_path: Path | None = None,
    cache_path: Path | None = None,
    data_dir: Path | None = None,
    sample: int | None = None,
) -> None:
    """Geocoding pipeline: prepare LINZ cache -> extract -> match -> write CSV.

    Parameters
    ----------
    sample:
        If set, randomly sample this many addresses before matching
        (useful for testing the LSH index on a smaller set).
    """
    pipeline_start = time.perf_counter()
    export_path = export_path or SETTINGS.geocode_export_path
    result_path = result_path or SETTINGS.geocode_result_path
    shp_path = shp_path or SETTINGS.linz_shp_path
    cache_path = cache_path or SETTINGS.linz_cache_path
    data_dir = data_dir or SETTINGS.raw_data_dir

    prepare_linz_cache(shp_path, cache_path)

    source_df = extract_addresses_from_csv(data_dir)
    if sample is not None and sample < len(source_df):
        source_df = source_df.sample(n=sample, random_state=42)
        logger.info("Sampled %d addresses for test run", len(source_df))
    write_csv(source_df, export_path)

    linz_norm = load_linz_norm(shp_path, cache_path)
    matches = match_addresses(source_df, linz_norm)
    write_csv(matches, result_path)

    elapsed = time.perf_counter() - pipeline_start
    logger.info("Geocoding pipeline completed in %.2f s", elapsed)
