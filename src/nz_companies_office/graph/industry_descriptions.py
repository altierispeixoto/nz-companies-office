"""Download ANZSIC 2006 reference spreadsheet and set descriptions on ancestor Industry nodes."""

from __future__ import annotations

import logging
import shutil
import tempfile
import urllib.request
from pathlib import Path

import xlrd

from nz_companies_office.config import SETTINGS
from nz_companies_office.db.connection import get_driver
from nz_companies_office.db.repository import Neo4jRepository

logger = logging.getLogger(__name__)

_ABS_URL = (
    "https://www.abs.gov.au/AUSSTATS/subscriber.nsf/log"
    "?openagent&1292.0.55.002_anzsic%202006%20-%20codes%20and%20titles.xls"
    "&1292.0.55.002&Data%20Cubes&A8CF900440465BDBCA257122001ABA2D"
    "&0&2006&28.02.2006&Latest"
)

_CACHE_DIR = "data/processed/anzsic"
_CACHE_FILE = "anzsic_2006_codes_and_titles.xls"

# Code-length ranges for each ANZSIC hierarchy level
_LEN_DIVISION = 1
_LEN_SUBDIVISION_MIN = 2
_LEN_SUBDIVISION_MAX = 3
_LEN_GROUP_MIN = 3
_LEN_GROUP_MAX = 4
_LEN_CLASS_MIN = 4
_LEN_CLASS_MAX = 5


def _download_xls(cache_dir: str | Path) -> Path:
    """Download the ANZSIC XLS if not already cached."""
    cache_path = Path(cache_dir) / _CACHE_FILE
    if cache_path.exists():
        logger.info("Using cached XLS: %s", cache_path)
        return cache_path

    cache_path.parent.mkdir(parents=True, exist_ok=True)

    with tempfile.NamedTemporaryFile(delete=False, suffix=".xls") as tmp:
        tmp_path = Path(tmp.name)
    try:
        logger.info("Downloading ANZSIC 2006 codes and titles from ABS...")
        urllib.request.urlretrieve(_ABS_URL, str(tmp_path))  # noqa: S310
        shutil.move(str(tmp_path), str(cache_path))
        logger.info("Saved to %s", cache_path)
    except Exception:
        tmp_path.unlink(missing_ok=True)
        raise

    return cache_path


def _parse_sheet(
    wb: xlrd.Book,
    sheet_index: int,
    code_col: int,
    title_col: int,
    min_len: int,
    max_len: int,
) -> dict[str, str]:
    """Parse one ANZSIC hierarchy sheet, tracking the current division."""
    sheet = wb.sheet_by_index(sheet_index)
    mapping: dict[str, str] = {}
    current_div = ""
    for r in range(sheet.nrows):
        div = str(sheet.cell_value(r, 1)).strip()
        code = str(sheet.cell_value(r, code_col)).strip()
        title = str(sheet.cell_value(r, title_col)).strip()
        if len(div) == _LEN_DIVISION and div.isalpha():
            current_div = div
        if current_div and min_len <= len(code) <= max_len and code.isdigit() and title:
            mapping[f"{current_div}{code}"] = title
    return mapping


def _parse_anzsic(xls_path: Path) -> dict[str, str]:
    """Parse the XLS and return a dict mapping code prefix to description.

    Includes all hierarchy levels:
      Division:     "A"       -> "Agriculture, Forestry and Fishing"
      Subdivision:  "A01"     -> "Agriculture"
      Group:        "A011"    -> "Nursery and Floriculture Production"
      Class:        "A0111"   -> "Nursery Production (Under Cover)"
    """
    wb = xlrd.open_workbook(str(xls_path))
    mapping: dict[str, str] = {}

    sheet = wb.sheet_by_index(1)
    for r in range(sheet.nrows):
        code = str(sheet.cell_value(r, 1)).strip()
        title = str(sheet.cell_value(r, 2)).strip()
        if len(code) == _LEN_DIVISION and code.isalpha() and title:
            mapping[code] = title

    mapping.update(_parse_sheet(wb, 2, 2, 3, _LEN_SUBDIVISION_MIN, _LEN_SUBDIVISION_MAX))
    mapping.update(_parse_sheet(wb, 3, 3, 4, _LEN_GROUP_MIN, _LEN_GROUP_MAX))
    mapping.update(_parse_sheet(wb, 4, 4, 5, _LEN_CLASS_MIN, _LEN_CLASS_MAX))

    return mapping


def _update_neo4j(mapping: dict[str, str], repo: Neo4jRepository) -> int:
    """Set description on Industry nodes whose code matches a known ANZSIC prefix."""
    updated = 0
    for code, description in mapping.items():
        result = repo.run_query(
            """
            MATCH (ind:Industry {code: $code})
            SET ind.description = $description
            RETURN count(*) AS cnt
            """,
            code=code,
            description=description,
        )
        if result and result[0]["cnt"] > 0:
            updated += result[0]["cnt"]

    return updated


def enrich_industry_descriptions(*, neo4j: bool = True) -> None:
    """Download ANZSIC reference and optionally update Neo4j.

    Args:
        neo4j: If True, update Industry node descriptions in Neo4j.
    """
    cache_dir = SETTINGS.project_root / _CACHE_DIR
    xls_path = _download_xls(cache_dir)
    mapping = _parse_anzsic(xls_path)

    logger.info("Parsed %d ANZSIC hierarchy entries from XLS", len(mapping))

    if neo4j:
        repo = Neo4jRepository(get_driver())
        if not repo.check_connectivity():
            logger.error("Cannot connect to Neo4j skipping database update")
            return

        updated = _update_neo4j(mapping, repo)
        logger.info("Updated descriptions on %d Industry nodes in Neo4j", updated)
    else:
        logger.info("Dry-run mode. %d descriptions would be applied:", len(mapping))
        for code, desc in sorted(mapping.items()):
            logger.info("  %s -> %s", code, desc)
