# ---
# marimo-version: 0.23.9
# license: Apache-2.0
# ---

import marimo

__generated_with = "0.23.10"
app = marimo.App(width="full")


@app.cell
def _():
    # Standard library
    import pathlib
    import warnings

    # Third-party
    import marimo as mo
    import pandas as pd
    import torch
    from torch_geometric.utils import degree

    # Local utilities
    from nz_companies_office.graph.builder import build_hetero_data
    from nz_companies_office.graph.extractor import GraphExtractor
    from nz_companies_office.graph.extractor import filter_removed_companies
    from nz_companies_office.graph.features import build_node_features
    from nz_companies_office.graph.split import sample_negative_edges
    from nz_companies_office.graph.split import split_share_edges

    warnings.filterwarnings("ignore")
    return (
        GraphExtractor,
        build_hetero_data,
        build_node_features,
        degree,
        filter_removed_companies,
        mo,
        pathlib,
        pd,
        sample_negative_edges,
        split_share_edges,
        torch,
    )


@app.cell
def _(mo):
    mo.md(r"""
    # NZ Companies Office — Dataset Pipeline

    Creates the heterogeneous graph dataset used by the **shareholder link prediction** model.

    **Output**: ``data/processed/pipeline_checkpoint/pipeline.pt``
    - Filters out ``REMOVED``-status companies.
    - Three ``HeteroData`` graphs: one per phase (train / validation / test), each with a
      different set of shareholder-company edges to prevent message-passing leakage.
    - Train/val/test splits of shareholder-to-company edges.
    - Negative samples (known non-edges) for evaluation.
    - Feature dimensions for instantiating the GNN model.
    """)
    return


@app.cell
def _(mo):
    mo.md(r"""
    ## 1. Database Connection

    The Neo4j database stores the NZ Companies Office graph with this schema:

    | Node Label | Key Properties |
    |---|---|
    | ``Company`` | company_number, name, status, entity_type, incorporation_date, nzbn |
    | ``Director`` | name, role, appointment_date |
    | ``Shareholder`` | name, share_count, share_type |
    | ``Industry`` | code, description |

    | Relationship | Direction |
    |---|---|
    | ``[:DIRECTS]`` | Director → Company |
    | ``[:HOLDS_SHARES_IN]`` | Shareholder → Company |
    | ``[:HAS_INDUSTRY]`` | Company → Industry |
    """)
    return


@app.cell
def _(GraphExtractor, mo):
    extractor = GraphExtractor()
    _connected = extractor._is_connected()
    mo.md(
        f"""
        **Neo4j Connection**: {"✅ Connected" if _connected else "⚠️ Not available"}

        URI: ``{extractor.uri}``

        Data source: cache file if present, otherwise live Neo4j query.
        """
    )
    return (extractor,)


@app.cell
def _(mo):
    mo.md(r"""
    ## 2. Graph Extraction

    Loads the graph from a cached checkpoint (seconds) or queries live Neo4j (minutes).
    """)
    return


@app.cell
def _(extractor):
    graph = extractor.extract(use_cache=True)
    return (graph,)


@app.cell
def _(extractor, graph):
    extractor.save_cache(graph)
    return


@app.cell
def _(filter_removed_companies, mo):
    n_before = graph.n_company
    graph = filter_removed_companies(graph)
    n_removed = n_before - graph.n_company
    mo.md(f"Removed **{n_removed}** companies with status ``REMOVED`` ({graph.n_company} companies remaining).")
    return (graph,)


@app.cell
def _(mo):
    mo.md(r"""
    ## 3. Dataset Exploration

    Quick overview of the extracted graph (after filtering out ``REMOVED`` companies).
    """)
    return


@app.cell
def _(graph, mo, pd):
    _node_df = pd.DataFrame(
        {
            "Node Type": ["Company", "Director", "Shareholder", "Industry"],
            "Count": [
                graph.n_company,
                graph.n_director,
                graph.n_shareholder,
                graph.n_industry,
            ],
        }
    )
    mo.ui.table(_node_df)
    return


@app.cell
def _(degree, graph, mo, pd):
    _dir_degree = degree(graph.dir_edge_index[1], num_nodes=graph.n_company).int()
    _share_degree = degree(graph.share_edge_index[1], num_nodes=graph.n_company).int()

    _company_df = pd.DataFrame(
        {
            "Name": graph.comp_names,
            "Status": graph.comp_statuses,
            "Entity Type": graph.comp_types,
            "# Directors": _dir_degree.numpy(),
            "# Shareholders": _share_degree.numpy(),
        }
    ).sort_values("# Shareholders", ascending=False)

    mo.ui.table(_company_df)
    return


@app.cell
def _(graph, mo, pd):
    _edge_df = pd.DataFrame(
        {
            "Relationship": [
                "Director → Company",
                "Shareholder → Company",
                "Company → Industry",
            ],
            "Edge Count": [
                graph.dir_edge_index.shape[1],
                graph.share_edge_index.shape[1],
                graph.ind_edge_index.shape[1],
            ],
            "Avg. Degree": [
                round(graph.dir_edge_index.shape[1] / max(graph.n_company, 1), 1),
                round(graph.share_edge_index.shape[1] / max(graph.n_company, 1), 1),
                round(graph.ind_edge_index.shape[1] / max(graph.n_company, 1), 1),
            ],
        }
    )
    mo.ui.table(_edge_df)
    return


@app.cell
def _(mo):
    mo.md(r"""
    ## 4. Node Feature Construction

    | Node Type | Features | Dimension |
    |---|---|---|
    | Company | status one-hot + entity-type one-hot + normalized director-degree | ~num_statuses + ~num_types + 1 |
    | Director | normalized director-degree + small random noise | ~num_statuses + ~num_types + 1 |
    | Shareholder | normalized shareholder-degree + small random noise | ~num_statuses + ~num_types + 1 |
    | Industry | normalized industry-degree + small random noise | ~num_statuses + ~num_types + 1 |

    Features are computed from the **full** graph (all remaining edges after filtering
    ``REMOVED`` companies). This is standard practice in transductive link prediction — the
    degree features provide a fixed structural prior, while the actual information leakage is
    isolated to the message-passing topology (handled next by building separate graphs per
    phase).
    """)
    return


@app.cell
def _(build_node_features, graph):
    (
        x_company,
        x_director,
        x_shareholder,
        n_company_feats,
        n_director_feats,
        n_shareholder_feats,
        x_industry,
        n_industry_feats,
    ) = build_node_features(
        comp_statuses=graph.comp_statuses,
        comp_types=graph.comp_types,
        dir_edge_index=graph.dir_edge_index,
        n_director=graph.n_director,
        n_company=graph.n_company,
        n_shareholder=graph.n_shareholder,
        share_edge_index=graph.share_edge_index,
        ind_edge_index=graph.ind_edge_index,
        n_industry=graph.n_industry,
    )
    return (
        n_company_feats,
        n_director_feats,
        n_industry_feats,
        n_shareholder_feats,
        x_company,
        x_director,
        x_industry,
        x_shareholder,
    )


@app.cell
def _(mo):
    mo.md(r"""
    ## 5. Edge Split — Preventing Data Leakage

    In transductive link prediction the **same nodes** are used in every phase, so the risk
    is that the encoder's message-passing step leaks information from held-out edges. To
    prevent this we first split all shareholder-company edges, then build **three separate
    graph objects** — each containing only the edges that phase is allowed to see:

    | Graph | Shareholder Edges Used | Used For |
    |---|---|---|
    | ``train_data`` | Training positives only | Message passing during training |
    | ``val_data`` | Training + validation positives | Encoding during validation |
    | ``test_data`` | All edges (training + validation + test) | Encoding during final evaluation |

    Director edges are **never split** — they are structural context available in all phases.
    """)
    return


@app.cell
def _(graph, split_share_edges):
    """First, randomly shuffle and partition edges into train/val/test sets."""
    training_edges, validation_edges, test_edges = split_share_edges(graph.share_edge_index)
    return test_edges, training_edges, validation_edges


@app.cell
def _(graph, mo, pd, test_edges, training_edges, validation_edges):
    _split_df = pd.DataFrame(
        {
            "Split": ["Train", "Validation", "Test"],
            "Positive Edges": [training_edges.shape[1], validation_edges.shape[1], test_edges.shape[1]],
            "Fraction": [
                f"{training_edges.shape[1] / graph.share_edge_index.shape[1] * 100:.1f}%",
                f"{validation_edges.shape[1] / graph.share_edge_index.shape[1] * 100:.1f}%",
                f"{test_edges.shape[1] / graph.share_edge_index.shape[1] * 100:.1f}%",
            ],
        }
    )
    mo.ui.table(_split_df)
    return


@app.cell
def _(mo):
    mo.md(r"""
    ## 6. Build Three Heterogeneous Graphs

    Each graph shares the same node features, director edges, and node names — only the
    shareholder-company edge set differs per phase.
    """)
    return


@app.cell
def _(
    build_hetero_data,
    graph,
    torch,
    training_edges,
    validation_edges,
    x_company,
    x_director,
    x_industry,
    x_shareholder,
):
    device = torch.device("cpu")

    # Training graph: only training shareholder edges
    train_data = build_hetero_data(
        x_company=x_company,
        x_director=x_director,
        x_shareholder=x_shareholder,
        n_company=graph.n_company,
        n_director=graph.n_director,
        n_shareholder=graph.n_shareholder,
        comp_names=graph.comp_names,
        share_names=graph.share_names,
        dir_names=graph.dir_names,
        dir_edge_index=graph.dir_edge_index,
        share_edge_index=training_edges,
        device=device,
        x_industry=x_industry,
        n_industry=graph.n_industry,
        ind_edge_index=graph.ind_edge_index,
    )

    # Validation graph: training + validation shareholder edges
    val_share_edges = torch.cat([training_edges, validation_edges], dim=1)
    val_data = build_hetero_data(
        x_company=x_company,
        x_director=x_director,
        x_shareholder=x_shareholder,
        n_company=graph.n_company,
        n_director=graph.n_director,
        n_shareholder=graph.n_shareholder,
        comp_names=graph.comp_names,
        share_names=graph.share_names,
        dir_names=graph.dir_names,
        dir_edge_index=graph.dir_edge_index,
        share_edge_index=val_share_edges,
        device=device,
        x_industry=x_industry,
        n_industry=graph.n_industry,
        ind_edge_index=graph.ind_edge_index,
    )

    # Test graph: all shareholder edges (full graph)
    test_data = build_hetero_data(
        x_company=x_company,
        x_director=x_director,
        x_shareholder=x_shareholder,
        n_company=graph.n_company,
        n_director=graph.n_director,
        n_shareholder=graph.n_shareholder,
        comp_names=graph.comp_names,
        share_names=graph.share_names,
        dir_names=graph.dir_names,
        dir_edge_index=graph.dir_edge_index,
        share_edge_index=graph.share_edge_index,
        device=device,
        x_industry=x_industry,
        n_industry=graph.n_industry,
        ind_edge_index=graph.ind_edge_index,
    )
    return test_data, train_data, val_data


@app.cell
def _(mo, test_data, train_data, val_data):
    _sz_trn = train_data["shareholder", "share", "company"].edge_index.shape[1]
    _sz_val = val_data["shareholder", "share", "company"].edge_index.shape[1]
    _sz_tst = test_data["shareholder", "share", "company"].edge_index.shape[1]

    mo.md(
        f"""
        **Graph Summary — Shareholder Edges Per Phase**

        | Graph | Shareholder Edges |
        |---|---|
        | ``train_data`` | {_sz_trn:,} |
        | ``val_data`` | {_sz_val:,} |
        | ``test_data`` | {_sz_tst:,} |

        Director edges ({test_data["director", "directs", "company"].edge_index.shape[1]:,}) and
        Industry edges ({test_data["company", "has_industry", "industry"].edge_index.shape[1]:,}) are
        identical across all three.
        """
    )
    return


@app.cell
def _(mo):
    mo.md(r"""
    ## 7. Negative Sampling for Evaluation

    Generate negative (non-existent) edges for validation and test metrics. Validation
    negatives exclude train positives; test negatives exclude train + validation positives
    — ensuring no evaluation overlap with edges the model has seen.
    """)
    return


@app.cell
def _(
    graph,
    sample_negative_edges,
    test_edges,
    training_edges,
    validation_edges,
):
    validation_negatives, test_negatives = sample_negative_edges(
        training_edges,
        validation_edges,
        test_edges,
        graph.n_shareholder,
        graph.n_company,
    )
    return test_negatives, validation_negatives


@app.cell
def _(
    mo,
    pd,
    test_edges,
    test_negatives,
    training_edges,
    validation_edges,
    validation_negatives,
):
    _stats_df = pd.DataFrame(
        {
            "Split": ["Train", "Validation", "Test"],
            "Positive Edges": [training_edges.shape[1], validation_edges.shape[1], test_edges.shape[1]],
            "Negative Edges": ["—", validation_negatives.shape[1], test_negatives.shape[1]],
            "Total for Evaluation": [
                "—",
                validation_edges.shape[1] + validation_negatives.shape[1],
                test_edges.shape[1] + test_negatives.shape[1],
            ],
        }
    )
    mo.ui.table(_stats_df)
    return


@app.cell
def _(
    n_company_feats,
    n_director_feats,
    n_industry_feats,
    n_shareholder_feats,
    pathlib,
    test_data,
    test_edges,
    test_negatives,
    torch,
    train_data,
    training_edges,
    val_data,
    validation_edges,
    validation_negatives,
):
    checkpoint_dir = pathlib.Path("data/processed/pipeline_checkpoint")
    checkpoint_dir.mkdir(parents=True, exist_ok=True)
    torch.save(
        {
            # Three separate graphs per phase to prevent message-passing leakage
            "train_data": train_data.cpu() if hasattr(train_data, "to") else train_data,
            "val_data": val_data.cpu() if hasattr(val_data, "to") else val_data,
            "test_data": test_data.cpu() if hasattr(test_data, "to") else test_data,
            # Backward-compatible alias for interactive testing notebook
            "data": test_data.cpu() if hasattr(test_data, "to") else test_data,
            # Edge split tensors
            "train_pos": training_edges.cpu(),
            "val_pos": validation_edges.cpu(),
            "test_pos": test_edges.cpu(),
            "val_neg": validation_negatives.cpu(),
            "test_neg": test_negatives.cpu(),
            # Feature dimensions
            "n_company_feats": n_company_feats,
            "n_director_feats": n_director_feats,
            "n_shareholder_feats": n_shareholder_feats,
            "n_industry_feats": n_industry_feats,
        },
        checkpoint_dir / "pipeline.pt",
    )
    return


@app.cell
def _(mo):
    mo.md(r"""
    ## Summary

    Pipeline checkpoint saved to ``data/processed/pipeline_checkpoint/pipeline.pt``.

    Run **01_link_prediction.py** next to train the GNN model and evaluate its
    link prediction performance.
    """)
    return


@app.cell
def _():
    return


if __name__ == "__main__":
    app.run()
