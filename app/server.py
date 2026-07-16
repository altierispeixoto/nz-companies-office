"""FastAPI server that queries Neo4j for the shareholder-company graph."""

from __future__ import annotations

import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Annotated

from fastapi import FastAPI
from fastapi import Query
from fastapi.middleware.cors import CORSMiddleware
from neo4j import GraphDatabase

NEO4J_URI = os.environ.get("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.environ.get("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.environ.get("NEO4J_PASSWORD", "password")

driver: GraphDatabase.driver | None = None  # type: ignore[reportGeneralTypeIssues]


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    global driver
    driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
    yield
    if driver:
        driver.close()


app = FastAPI(title="NZ Companies Graph API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/graph")
async def get_graph(
    status: Annotated[str | None, Query(description="Filter company status (e.g. Registered)")] = None,
    limit: Annotated[int, Query(ge=1, le=50000, description="Max edges to return")] = 2000,
    min_connections: Annotated[int, Query(ge=0, le=1000, description="Min shareholder connections for a company")] = 1,
) -> dict:
    """Return nodes + links for the shareholder→company graph."""
    if not driver:
        return {"error": "Neo4j not connected"}

    with driver.session() as session:
        # --- edges ---
        params: dict = {"limit": limit, "min_connections": min_connections}
        status_clause = ""
        if status:
            status_clause = "AND toUpper(c.status) = toUpper($status) "
            params["status"] = status

        edges_query = f"""
            MATCH (c:Company)
            WHERE 1=1 {status_clause}
            MATCH (c)<-[:HOLDS_SHARES_IN]-(s:Shareholder)
            WITH c, COUNT(DISTINCT s) AS total_shareholders
            WHERE total_shareholders >= $min_connections
            ORDER BY total_shareholders DESC
            MATCH (c)<-[:HOLDS_SHARES_IN]-(share:Shareholder)
            RETURN share.name AS src_name, c.company_number AS dst_id,
                   c.name AS dst_name, c.status AS dst_status, total_shareholders
        """
        edges_result = session.run(edges_query, **params).data()

    # Build unique node sets
    company_map: dict[str, dict] = {}
    shareholder_map: dict[str, dict] = {}
    links: list[dict] = []

    row: dict
    for row in edges_result:
        src = row["src_name"]
        dst_id = row["dst_id"]
        dst_name = row["dst_name"]
        dst_status = row["dst_status"]
        weight = row.get("total_shareholders", 1)

        if dst_id not in company_map:
            company_map[dst_id] = {"id": f"c{dst_id}", "name": dst_name, "type": "company", "status": dst_status}
        if src not in shareholder_map:
            shareholder_map[src] = {"id": f"s{src}", "name": src, "type": "shareholder"}

        links.append(
            {
                "source": f"s{src}",
                "target": f"c{dst_id}",
                "weight": weight,
                "total_shareholders": weight,
            },
        )

    nodes = list(shareholder_map.values()) + list(company_map.values())

    return {
        "nodes": nodes,
        "links": links,
        "meta": {
            "node_count": len(nodes),
            "link_count": len(links),
            "company_count": len(company_map),
            "shareholder_count": len(shareholder_map),
        },
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("server:app", host="0.0.0.0", port=8000, reload=True)
