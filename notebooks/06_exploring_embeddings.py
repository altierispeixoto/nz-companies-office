# ---
# marimo-version: 0.23.9
# license: Apache-2.0
# ---

import marimo

__generated_with = "0.23.10"
app = marimo.App(width="full")


@app.cell
def _():
    import contextlib
    import json
    import logging
    import pathlib
    import warnings

    import marimo as mo
    import numpy as np
    import torch
    from sklearn.decomposition import PCA
    from torch_geometric.utils import degree

    from nz_companies_office.models.builder import build_hetero_data
    from nz_companies_office.models.extractor import GraphExtractor
    from nz_companies_office.models.features import build_exploration_features
    from nz_companies_office.models.link_predictor import LinkPredictor
    from nz_companies_office.models.split import sample_negative_edges
    from nz_companies_office.models.split import split_share_edges
    from nz_companies_office.models.trainer import LinkPredictorTrainer

    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger(__name__)
    warnings.filterwarnings("ignore")

    enough_mem: bool = False
    free_mem: float = 0.0
    if torch.cuda.is_available():
        free_mem = torch.cuda.get_device_properties(0).total_memory - torch.cuda.memory_allocated(0)
        enough_mem = free_mem > 8e9
    device = torch.device("cuda" if (torch.cuda.is_available() and enough_mem) else "cpu")
    status = f"CUDA free: {free_mem/1e9:.1f}GB" if torch.cuda.is_available() else "no CUDA"
    mo.output.append(mo.md(f"**Device**: {device} | {status}"))

    if not enough_mem:
        mo.output.append(
            mo.md(
                "**Note**: GPU memory insufficient for full graph. "
                "Falling back to CPU. Training will be slower (~30-60 min)."
            )
        )
    return (
        GraphExtractor,
        LinkPredictor,
        LinkPredictorTrainer,
        PCA,
        build_exploration_features,
        build_hetero_data,
        contextlib,
        degree,
        device,
        json,
        logger,
        mo,
        np,
        pathlib,
        sample_negative_edges,
        split_share_edges,
        torch,
    )


@app.cell
def _(mo):
    mo.md("""
    ## 1. Extract Graph from Neo4j
    """)
    return


@app.cell
def _(GraphExtractor, logger):
    extractor = GraphExtractor()
    graph = extractor.extract(use_cache=True)
    logger.info(
        "Graph extracted: %d companies, %d directors, %d shareholders, %d industries",
        graph.n_company,
        graph.n_director,
        graph.n_shareholder,
        graph.n_industry,
    )
    return (graph,)


@app.cell
def _(mo):
    mo.md("""
    ## 2. Build Exploration Features (no status)
    """)
    return


@app.cell
def _(build_exploration_features, graph):
    feats = build_exploration_features(
        comp_types=graph.comp_types,
        incorporation_dates=graph.incorporation_dates,
        dir_edge_index=graph.dir_edge_index,
        n_director=graph.n_director,
        n_company=graph.n_company,
        n_shareholder=graph.n_shareholder,
        share_edge_index=graph.share_edge_index,
        ind_edge_index=graph.ind_edge_index,
        n_industry=graph.n_industry,
        industry_descriptions=graph.industry_descriptions,
    )
    (
        x_company,
        x_director,
        x_shareholder,
        n_comp_feats,
        n_dir_feats,
        n_share_feats,
        x_industry,
        n_ind_feats,
    ) = feats

    print(f"Company features:  {x_company.shape}  ({n_comp_feats} dims)")
    print(f"Director features: {x_director.shape}  ({n_dir_feats} dims)")
    print(f"Shareholder features: {x_shareholder.shape}  ({n_share_feats} dims)")
    print(f"Industry features: {x_industry.shape if x_industry is not None else None}  ({n_ind_feats} dims)")
    return (
        n_comp_feats,
        n_dir_feats,
        n_ind_feats,
        n_share_feats,
        x_company,
        x_director,
        x_industry,
        x_shareholder,
    )


@app.cell
def _(mo):
    mo.md("""
    ## 3. Build HeteroData (Full Graph)
    """)
    return


@app.cell
def _(
    build_hetero_data,
    device,
    graph,
    x_company,
    x_director,
    x_industry,
    x_shareholder,
):
    data = build_hetero_data(
        x_company=x_company,
        x_director=x_director,
        x_shareholder=x_shareholder,
        n_company=graph.n_company,
        n_director=graph.n_director,
        n_shareholder=graph.n_shareholder,
        comp_names=graph.comp_names,
        dir_names=graph.dir_names,
        share_names=graph.share_names,
        dir_edge_index=graph.dir_edge_index,
        share_edge_index=graph.share_edge_index,
        device=device,
        x_industry=x_industry,
        n_industry=graph.n_industry,
        ind_edge_index=graph.ind_edge_index,
    )
    print(f"HeteroData: {data}")
    return (data,)


@app.cell
def _(mo):
    mo.md("""
    ## 4. Split Edges & Train LinkPredictor
    """)
    return


@app.cell
def _(
    LinkPredictor,
    LinkPredictorTrainer,
    data,
    device,
    graph,
    logger,
    mo,
    n_comp_feats,
    n_dir_feats,
    n_ind_feats,
    n_share_feats,
    sample_negative_edges,
    split_share_edges,
    torch,
):
    train_pos, val_pos, test_pos = split_share_edges(graph.share_edge_index, train_ratio=0.85, val_ratio=0.075)
    val_neg, test_neg = sample_negative_edges(
        train_pos,
        val_pos,
        test_pos,
        n_shareholder=graph.n_shareholder,
        n_company=graph.n_company,
    )
    logger.info(
        "Edge split: %d train, %d val, %d test",
        train_pos.shape[1],
        val_pos.shape[1],
        test_pos.shape[1],
    )

    model = LinkPredictor(
        dir_feats=n_dir_feats,
        comp_feats=n_comp_feats,
        share_feats=n_share_feats,
        ind_feats=n_ind_feats,
        hidden_dim=32,
        out_dim=16,
    )
    model = model.to(device)
    optimizer = torch.optim.Adam(model.parameters(), lr=0.01)

    trainer = LinkPredictorTrainer(
        model=model,
        optimizer=optimizer,
        train_data=data,
        val_data=data,
        test_data=data,
        training_edges=train_pos,
        validation_edges=val_pos,
        validation_negatives=val_neg,
        checkpoint_directory=None,
    )

    mo.output.append(mo.md("**Training started...**"))

    result = trainer.train(num_epochs=50, patience=10)

    mo.output.append(
        mo.md(
            f"**Training done**: Best val AUC = {result.best_validation_auc:.4f} "
            f"at epoch {result.best_epoch} "
            f"({'stopped early' if result.stopped_early else 'completed all epochs'})"
        )
    )

    test_result = trainer.evaluate(test_pos, test_neg)
    mo.output.append(mo.md(f"**Test**: AUC = {test_result.auc:.4f}, AP = {test_result.average_precision:.4f}"))
    return model, result, test_result


@app.cell
def _(mo):
    mo.md("""
    ## 5. Encode All Companies
    """)
    return


@app.cell
def _(data, model, torch):
    model.eval()
    with torch.no_grad():
        x_dict = model.encode(data)
        company_embeddings_gnn = x_dict["company"].cpu().numpy()
    print(f"GNN embeddings: {company_embeddings_gnn.shape}")
    return (company_embeddings_gnn,)


@app.cell
def _(mo):
    mo.md("""
    ## 6. Stratified Sample ~50K Companies
    """)
    return


@app.cell
def _(company_embeddings_gnn, degree, graph, logger, mo, np, x_company):
    statuses = [s.upper() for s in graph.comp_statuses]
    n = len(statuses)
    indices = np.arange(n)

    rare_mask = np.array([s not in ("REGISTERED", "REMOVED") for s in statuses])
    registered_mask = np.array([s == "REGISTERED" for s in statuses])
    removed_mask = np.array([s == "REMOVED" for s in statuses])

    rare_idx = indices[rare_mask]
    registered_idx = indices[registered_mask]
    removed_idx = indices[removed_mask]

    rng = np.random.default_rng(42)

    n_rare = len(rare_idx)
    n_reg = min(15000, len(registered_idx))
    n_rem = min(15000, len(removed_idx))
    n_fill = max(0, 50000 - n_rare - n_reg - n_rem)

    sampled_reg = rng.choice(registered_idx, size=n_reg, replace=False)
    sampled_rem = rng.choice(removed_idx, size=n_rem, replace=False)

    remaining = np.setdiff1d(indices, np.concatenate([sampled_reg, sampled_rem, rare_idx]))
    sampled_fill = rng.choice(remaining, size=min(n_fill, len(remaining)), replace=False)

    sample_idx = np.concatenate([sampled_reg, sampled_rem, rare_idx, sampled_fill])
    rng.shuffle(sample_idx)

    logger.info(
        "Sampled %d companies: %d Registered, %d Removed, %d rare, %d fill",
        len(sample_idx),
        n_reg,
        n_rem,
        n_rare,
        len(sampled_fill),
    )

    sample_emb_gnn = company_embeddings_gnn[sample_idx]
    sample_features = x_company[sample_idx].cpu().numpy()
    sample_comp_names = [graph.comp_names[i] for i in sample_idx]
    sample_comp_numbers = [graph.comp_numbers[i] for i in sample_idx]
    sample_statuses = [graph.comp_statuses[i] for i in sample_idx]
    sample_types = [graph.comp_types[i] for i in sample_idx]
    sample_dates = [graph.incorporation_dates[i] for i in sample_idx]

    comp_dir_deg = degree(graph.dir_edge_index[1], num_nodes=graph.n_company)
    comp_share_deg = degree(graph.share_edge_index[1], num_nodes=graph.n_company)
    sample_dir_deg = [int(comp_dir_deg[i].item()) for i in sample_idx]
    sample_share_deg = [int(comp_share_deg[i].item()) for i in sample_idx]

    mo.output.append(mo.md(f"**Sample**: {len(sample_idx)} companies (statuses: {len(set(sample_statuses))} unique)"))
    return (
        sample_comp_names,
        sample_comp_numbers,
        sample_dates,
        sample_dir_deg,
        sample_emb_gnn,
        sample_features,
        sample_idx,
        sample_share_deg,
        sample_statuses,
        sample_types,
    )


@app.cell
def _(mo):
    mo.md("""
    ## 7. Experiment A — PCA Baseline (Raw Features)
    """)
    return


@app.cell
def _(PCA, sample_features):
    n_pca = min(16, sample_features.shape[1])
    pca = PCA(n_components=n_pca, random_state=42)
    sample_emb_pca = pca.fit_transform(sample_features)
    print(f"PCA embeddings: {sample_emb_pca.shape}  (explained var: {pca.explained_variance_ratio_.sum():.3f}, n_feats={sample_features.shape[1]})")
    return (sample_emb_pca,)


@app.cell
def _(mo):
    mo.md("""
    ## 8. Experiment B — Random GNN Baseline
    """)
    return


@app.cell
def _(
    LinkPredictor,
    build_hetero_data,
    device,
    graph,
    n_comp_feats,
    n_dir_feats,
    n_ind_feats,
    n_share_feats,
    sample_idx,
    torch,
    x_company,
    x_director,
    x_industry,
    x_shareholder,
):
    model_random = LinkPredictor(
        dir_feats=n_dir_feats,
        comp_feats=n_comp_feats,
        share_feats=n_share_feats,
        ind_feats=n_ind_feats,
        hidden_dim=32,
        out_dim=16,
    )
    model_random = model_random.to(torch.device("cpu"))
    model_random.eval()

    data_random = build_hetero_data(
        x_company=x_company,
        x_director=x_director,
        x_shareholder=x_shareholder,
        n_company=graph.n_company,
        n_director=graph.n_director,
        n_shareholder=graph.n_shareholder,
        comp_names=graph.comp_names,
        dir_names=graph.dir_names,
        share_names=graph.share_names,
        dir_edge_index=graph.dir_edge_index,
        share_edge_index=graph.share_edge_index,
        device=device,
        x_industry=x_industry,
        n_industry=graph.n_industry,
        ind_edge_index=graph.ind_edge_index,
    )

    with torch.no_grad():
        x_dict_random = model_random.encode(data_random)
        company_embeddings_random = x_dict_random["company"].cpu().numpy()

    sample_emb_random = company_embeddings_random[sample_idx]
    print(f"Random GNN embeddings: {company_embeddings_random.shape}")
    return (sample_emb_random,)


@app.cell
def _(mo):
    mo.md("""
    ## 9. Build Metadata
    """)
    return


@app.cell
def _(
    contextlib,
    graph,
    sample_comp_names,
    sample_comp_numbers,
    sample_dates,
    sample_dir_deg,
    sample_idx,
    sample_share_deg,
    sample_statuses,
    sample_types,
):
    company_to_divisions: dict[int, set[str]] = {}
    ind_src = graph.ind_edge_index[0].numpy()
    ind_dst = graph.ind_edge_index[1].numpy()
    for src, dst in zip(ind_src, ind_dst, strict=False):
        code = graph.industry_codes[dst]
        if code:
            company_to_divisions.setdefault(int(src), set()).add(code[0])
    industry_division_map = {
        i: "|".join(sorted(company_to_divisions.get(int(i), set()))) or "None"
        for i in sample_idx
    }

    metadata = []
    for idx_in_sample, orig_idx in enumerate(sample_idx):
        inc_year = None
        d = sample_dates[idx_in_sample]
        if d is not None and len(d) >= 4:
            with contextlib.suppress(ValueError):
                inc_year = int(d[:4])

        metadata.append(
            {
                "id": sample_comp_numbers[idx_in_sample],
                "name": sample_comp_names[idx_in_sample],
                "status": sample_statuses[idx_in_sample],
                "entity_type": sample_types[idx_in_sample],
                "incorporation_year": inc_year,
                "industry_division": industry_division_map[orig_idx],
                "director_count": sample_dir_deg[idx_in_sample],
                "shareholder_count": sample_share_deg[idx_in_sample],
                "is_isolated": sample_dir_deg[idx_in_sample] == 0 and sample_share_deg[idx_in_sample] == 0,
            }
        )

    print(f"Metadata rows: {len(metadata)}")
    print(f"Statuses present: {sorted({m['status'] for m in metadata})}")
    print(f"Isolated companies: {sum(1 for m in metadata if m['is_isolated'])}")
    return (metadata,)


@app.cell
def _(mo):
    mo.md("""
    ## 10. Export to Embedding Atlas JSON
    """)
    return


@app.cell
def _(
    json,
    metadata,
    pathlib,
    sample_emb_gnn,
    sample_emb_pca,
    sample_emb_random,
):
    output_dir = pathlib.Path("data/processed")
    output_dir.mkdir(parents=True, exist_ok=True)

    def _build_rows(embeddings, name):
        rows = []
        for i, m in enumerate(metadata):
            row = dict(m)
            for d in range(embeddings.shape[1]):
                row[f"dim_{d}"] = float(embeddings[i, d])
            rows.append(row)
        path = output_dir / f"embeddings_{name}.json"
        with path.open("w") as f:
            json.dump(rows, f, indent=2)
        return path

    path_a = _build_rows(sample_emb_pca, "pca")
    path_b = _build_rows(sample_emb_random, "random")
    path_c = _build_rows(sample_emb_gnn, "gnn")

    print("Exported:")
    print(f"  A (PCA):        {path_a}  ({len(metadata)} rows)")
    print(f"  B (Random GNN): {path_b}  ({len(metadata)} rows)")
    print(f"  C (Trained GNN): {path_c}  ({len(metadata)} rows)")
    return


@app.cell
def _(
    device,
    graph,
    metadata,
    result,
    sample_emb_gnn,
    sample_emb_pca,
    sample_emb_random,
    test_result,
):
    print("=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print(f"Device: {device}")
    print(f"Total companies in graph: {graph.n_company}")
    print(f"Total directors: {graph.n_director}")
    print(f"Total shareholders: {graph.n_shareholder}")
    print(f"Total industries: {graph.n_industry}")
    print(f"Link-prediction val AUC: {result.best_validation_auc:.4f}")
    print(f"Link-prediction test AUC: {test_result.auc:.4f}")
    print(f"Link-prediction test AP:  {test_result.average_precision:.4f}")
    print(f"Sampled companies: {len(metadata)}")
    print(f"Embedding dim: {sample_emb_gnn.shape[1]}")
    print(f"PCA explained variance: {sample_emb_pca.shape}")
    print(f"Random GNN emb range: [{sample_emb_random.min():.3f}, {sample_emb_random.max():.3f}]")
    print(f"Trained GNN emb range: [{sample_emb_gnn.min():.3f}, {sample_emb_gnn.max():.3f}]")
    print()
    print("Files ready for Embedding Atlas:")
    print("  - data/processed/embeddings_pca.json    (A: PCA baseline)")
    print("  - data/processed/embeddings_random.json  (B: Random GNN)")
    print("  - data/processed/embeddings_gnn.json     (C: Trained GNN)")
    print()
    print("Open Embedding Atlas and load each file as a separate layer.")
    print("Color by 'status' (test) or 'industry_division' (control).")
    print("Shape by 'entity_type'.")
    return


if __name__ == "__main__":
    app.run()
