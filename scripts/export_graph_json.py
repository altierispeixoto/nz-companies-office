"""Export the cached PyTorch graph to a JSON file for the Cosmograph web app."""

from __future__ import annotations

import json
from pathlib import Path

import torch

CACHE_PATH = Path("data/processed/nz_companies.pt")
OUTPUT_PATH = Path("app/src/data.json")


def export_graph_json() -> None:
    """Load the cached graph and write nodes + links as JSON."""
    print(f"Loading {CACHE_PATH}...")
    data = torch.load(CACHE_PATH, map_location="cpu", weights_only=True)

    comp_names: list[str] = data["comp_names"]
    share_names: list[str] = data["share_names"]
    comp_statuses: list[str] = data.get("comp_statuses", [])
    share_edge_index = data["share_edge_index"]

    n_companies = len(comp_names)
    n_shareholders = len(share_names)
    n_edges = share_edge_index.size(1)
    print(f"  Companies:   {n_companies}")
    print(f"  Shareholders: {n_shareholders}")
    print(f"  Edges:        {n_edges}")

    # Determine which nodes actually participate in edges
    company_ids: set[int] = set()
    shareholder_ids: set[int] = set()
    for i in range(n_edges):
        shareholder_ids.add(int(share_edge_index[0, i]))
        company_ids.add(int(share_edge_index[1, i]))

    print(f"  Companies with shareholders: {len(company_ids)}")
    print(f"  Shareholders with holdings:  {len(shareholder_ids)}")

    # Build nodes array
    nodes: list[dict] = []
    for comp_idx in sorted(company_ids):
        status = comp_statuses[comp_idx] if comp_idx < len(comp_statuses) else "Unknown"
        nodes.append(
            {
                "id": f"c{comp_idx}",
                "name": comp_names[comp_idx],
                "type": "company",
                "status": status,
            }
        )
    for share_idx in sorted(shareholder_ids):
        nodes.append(
            {
                "id": f"s{share_idx}",
                "name": share_names[share_idx],
                "type": "shareholder",
            }
        )

    # Build node-id → index map (for links)
    node_index: dict[str, int] = {n["id"]: i for i, n in enumerate(nodes)}

    # Build links array
    links: list[dict] = []
    for i in range(n_edges):
        share_idx = int(share_edge_index[0, i])
        comp_idx = int(share_edge_index[1, i])
        src = f"s{share_idx}"
        tgt = f"c{comp_idx}"
        if src in node_index and tgt in node_index:
            links.append(
                {
                    "source": src,
                    "target": tgt,
                    "sourceidx": node_index[src],
                    "targetidx": node_index[tgt],
                }
            )

    graph = {"nodes": nodes, "links": links}

    print(f"  Output nodes: {len(nodes)}")
    print(f"  Output links: {len(links)}")

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_PATH, "w") as f:
        json.dump(graph, f)

    file_size = OUTPUT_PATH.stat().st_size
    print(f"Written {OUTPUT_PATH} ({file_size / 1_000_000:.1f} MB)")


if __name__ == "__main__":
    export_graph_json()
