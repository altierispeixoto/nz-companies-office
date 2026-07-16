"""Graph extraction from Neo4j (or cache) for the investor network."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

import torch

try:
    from neo4j import GraphDatabase as _GraphDatabase

    _HAS_NEO4J = True
except ImportError:
    _HAS_NEO4J = False


@dataclass
class ExtractedGraph:
    """Container for raw graph data extracted from Neo4j.

    Attributes:
        comp_names: Human-readable company names.
        dir_names: Human-readable director names.
        share_names: Human-readable shareholder names.
        comp_statuses: Company status strings (e.g. "Registered").
        comp_types: Company entity type strings (e.g. "NZ Limited").
        industry_codes: Industry classification codes (e.g. "A011101").
        industry_descriptions: Human-readable descriptions of industry classes.
        dir_edge_index: 2xE director->company edge index.
        share_edge_index: 2xE shareholder->company edge index.
        ind_edge_index: 2xE company->industry edge index.

    """

    comp_names: list[str]
    dir_names: list[str]
    share_names: list[str]
    comp_statuses: list[str]
    comp_types: list[str]
    industry_codes: list[str]
    industry_descriptions: list[str]
    dir_edge_index: torch.LongTensor
    share_edge_index: torch.LongTensor
    ind_edge_index: torch.LongTensor

    @property
    def n_company(self) -> int:
        """Number of company nodes."""
        return len(self.comp_names)

    @property
    def n_director(self) -> int:
        """Number of director nodes."""
        return len(self.dir_names)

    @property
    def n_shareholder(self) -> int:
        """Number of shareholder nodes."""
        return len(self.share_names)

    @property
    def n_industry(self) -> int:
        """Number of industry nodes."""
        return len(self.industry_codes)


class GraphExtractor:
    """Extracts graph data from Neo4j or a cached checkpoint.

    Provides two extraction paths:
        1. **Cache** — loads a previously saved ``.pt`` file (fastest).
        2. **Neo4j** — live extraction from a running database instance.

    """

    CACHE_PATH = Path("data/processed/nz_companies.pt")

    def __init__(
        self,
        uri: str = "bolt://localhost:7687",
        user: str = "neo4j",
        password: str | None = None,
    ) -> None:
        """Initialise the extractor with Neo4j connection parameters.

        Args:
            uri: Bolt URI for the Neo4j instance.
            user: Neo4j username.
            password: Neo4j password. Falls back to ``NEO4J_PASSWORD`` env var
                or ``"password"``.

        """
        self.uri = uri
        self.user = user
        self.password = password or os.environ.get("NEO4J_PASSWORD", "password")

    def extract(self, *, use_cache: bool = True) -> ExtractedGraph:
        """Extract the graph, trying cache first then fall back to Neo4j.

        Args:
            use_cache: Whether to attempt loading from ``CACHE_PATH``.

        Returns:
            Populated ``ExtractedGraph`` instance.

        Raises:
            RuntimeError: If neither cache nor Neo4j connection is available.

        """
        if use_cache and self.CACHE_PATH.exists():
            return self._load_cache()
        if self._is_connected():
            return self._extract_neo4j()
        _msg = (
            "No cache found and unable to connect to Neo4j. "
            "Start the database with ``docker compose up -d`` or supply a cache file."
        )
        raise RuntimeError(_msg)

    def save_cache(self, graph: ExtractedGraph) -> None:
        """Persist an extracted graph to the cache file for fast reload.

        Args:
            graph: The ``ExtractedGraph`` instance to persist.

        """
        self.CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
        torch.save(
            {
                "comp_names": graph.comp_names,
                "dir_names": graph.dir_names,
                "share_names": graph.share_names,
                "comp_statuses": graph.comp_statuses,
                "comp_types": graph.comp_types,
                "industry_codes": graph.industry_codes,
                "industry_descriptions": graph.industry_descriptions,
                "dir_edge_index": graph.dir_edge_index,
                "share_edge_index": graph.share_edge_index,
                "ind_edge_index": graph.ind_edge_index,
            },
            self.CACHE_PATH,
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _is_connected(self) -> bool:
        if not _HAS_NEO4J:
            return False
        try:
            _driver = _GraphDatabase.driver(self.uri, auth=(self.user, self.password))
            _driver.verify_connectivity()
            _driver.close()
        except BaseException:  # noqa: BLE001
            return False
        return True

    def _load_cache(self) -> ExtractedGraph:
        cached = torch.load(self.CACHE_PATH, map_location="cpu")
        dir_names = cached.get(
            "dir_names",
            [f"Director {i}" for i in range(cached.get("n_director", len(cached["comp_names"])))],
        )
        share_names = cached.get(
            "share_names",
            [f"Shareholder {i}" for i in range(cached.get("n_shareholder", len(cached["comp_names"])))],
        )
        industry_codes = cached.get("industry_codes", [])
        industry_descriptions = cached.get("industry_descriptions", [])
        ind_edge_index = cached.get(
            "ind_edge_index",
            torch.empty(2, 0, dtype=torch.long),
        )
        return ExtractedGraph(
            comp_names=cached["comp_names"],
            dir_names=dir_names,
            share_names=share_names,
            comp_statuses=cached["comp_statuses"],
            comp_types=cached["comp_types"],
            industry_codes=industry_codes,
            industry_descriptions=industry_descriptions,
            dir_edge_index=cached["dir_edge_index"],
            share_edge_index=cached["share_edge_index"],
            ind_edge_index=ind_edge_index,
        )

    @staticmethod
    def _normalise(name: str) -> str:
        """Collapse whitespace in a string for consistent ID matching."""
        return " ".join(name.split())

    def _extract_neo4j(self) -> ExtractedGraph:
        _driver = _GraphDatabase.driver(self.uri, auth=(self.user, self.password))

        def _query(query: str) -> list[dict]:
            with _driver.session() as session:
                return session.run(query).data()

        # --- fetch node records -----------------------------------------------
        company_records = _query(
            "MATCH (c:Company) RETURN c.company_number AS id, c.name AS name, "
            "c.status AS status, c.entity_type AS entity_type",
        )
        director_records = _query("MATCH (d:Director) RETURN d.name AS id, d.name AS name")
        shareholder_records = _query("MATCH (s:Shareholder) RETURN s.name AS id, s.name AS name")
        industry_records = _query(
            "MATCH (ind:Industry) RETURN ind.code AS id, ind.code AS name, ind.description AS description",
        )

        # --- fetch edge records -----------------------------------------------
        directs_raw = _query(
            "MATCH (d:Director)-[:DIRECTS]->(c:Company) RETURN d.name AS src, c.company_number AS dst",
        )
        shares_raw = _query(
            "MATCH (s:Shareholder)-[:HOLDS_SHARES_IN]->(c:Company) RETURN s.name AS src, c.company_number AS dst",
        )
        industry_rels_raw = _query(
            "MATCH (c:Company)-[:HAS_INDUSTRY]->(ind:Industry) RETURN c.company_number AS src, ind.code AS dst",
        )
        _driver.close()

        # --- extract scalar fields --------------------------------------------
        comp_names = [r["name"] for r in company_records]
        comp_statuses = [r["status"] for r in company_records]
        comp_types = [r["entity_type"] for r in company_records]
        dir_names = [r["name"] for r in director_records]
        share_names = [r["name"] for r in shareholder_records]
        industry_codes = [r["id"] for r in industry_records]
        industry_descriptions = [r["description"] or "" for r in industry_records]

        # --- build id → index maps --------------------------------------------
        _norm = self._normalise

        comp_index = {_norm(r["id"]): i for i, r in enumerate(company_records)}
        dir_index = {_norm(r["id"]): i for i, r in enumerate(director_records)}
        share_index = {_norm(r["id"]): i for i, r in enumerate(shareholder_records)}
        ind_index = {_norm(r["id"]): i for i, r in enumerate(industry_records)}

        # --- construct edge_index tensors -------------------------------------
        def _valid(edge: dict, id_map: dict[str, int]) -> bool:
            return _norm(edge["src"]) in id_map and _norm(edge["dst"]) in comp_index

        dir_valid = [e for e in directs_raw if _valid(e, dir_index)]
        dir_edge_index = torch.tensor(
            [
                [dir_index[_norm(e["src"])] for e in dir_valid],
                [comp_index[_norm(e["dst"])] for e in dir_valid],
            ],
            dtype=torch.long,
        )

        share_valid = [e for e in shares_raw if _valid(e, share_index)]
        share_edge_index = (
            torch.tensor(
                [
                    [share_index[_norm(e["src"])] for e in share_valid],
                    [comp_index[_norm(e["dst"])] for e in share_valid],
                ],
                dtype=torch.long,
            )
            if share_valid
            else torch.empty(2, 0, dtype=torch.long)
        )

        # --- construct industry edge_index tensor -----------------------------
        ind_valid = [e for e in industry_rels_raw if _norm(e["src"]) in comp_index and _norm(e["dst"]) in ind_index]
        ind_edge_index = (
            torch.tensor(
                [
                    [comp_index[_norm(e["src"])] for e in ind_valid],
                    [ind_index[_norm(e["dst"])] for e in ind_valid],
                ],
                dtype=torch.long,
            )
            if ind_valid
            else torch.empty(2, 0, dtype=torch.long)
        )

        return ExtractedGraph(
            comp_names=comp_names,
            dir_names=dir_names,
            share_names=share_names,
            comp_statuses=comp_statuses,
            comp_types=comp_types,
            industry_codes=industry_codes,
            industry_descriptions=industry_descriptions,
            dir_edge_index=dir_edge_index,
            share_edge_index=share_edge_index,
            ind_edge_index=ind_edge_index,
        )


def filter_removed_companies(graph: ExtractedGraph) -> ExtractedGraph:
    """Return a new ``ExtractedGraph`` with REMOVED-status companies excluded.

    Company nodes whose status (case-insensitive) equals ``"REMOVED"`` are
    dropped along with their incident director and shareholder edges. Company
    node indices are remapped to be contiguous; director and shareholder nodes
    are unchanged.

    Args:
        graph: Source ``ExtractedGraph`` (not modified).

    Returns:
        A new ``ExtractedGraph`` containing only non-removed companies.

    """
    kept_mask = torch.tensor([s.upper() != "REMOVED" for s in graph.comp_statuses])
    kept_indices = torch.where(kept_mask)[0]
    old_to_new = torch.full((graph.n_company,), -1, dtype=torch.long)
    old_to_new[kept_indices] = torch.arange(len(kept_indices))

    dir_mask = kept_mask[graph.dir_edge_index[1]]
    dir_edge_index = graph.dir_edge_index[:, dir_mask].clone()
    dir_edge_index[1] = old_to_new[dir_edge_index[1]]

    share_mask = kept_mask[graph.share_edge_index[1]]
    share_edge_index = graph.share_edge_index[:, share_mask].clone()
    share_edge_index[1] = old_to_new[share_edge_index[1]]

    ind_mask = kept_mask[graph.ind_edge_index[0]]
    ind_edge_index = graph.ind_edge_index[:, ind_mask].clone()
    ind_edge_index[0] = old_to_new[ind_edge_index[0]]

    return ExtractedGraph(
        comp_names=[n for i, n in enumerate(graph.comp_names) if kept_mask[i]],
        dir_names=list(graph.dir_names),
        share_names=list(graph.share_names),
        comp_statuses=[s for i, s in enumerate(graph.comp_statuses) if kept_mask[i]],
        comp_types=[t for i, t in enumerate(graph.comp_types) if kept_mask[i]],
        industry_codes=list(graph.industry_codes),
        industry_descriptions=list(graph.industry_descriptions),
        dir_edge_index=dir_edge_index,
        share_edge_index=share_edge_index,
        ind_edge_index=ind_edge_index,
    )
