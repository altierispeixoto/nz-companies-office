# ---
# marimo-version: 0.23.9
# license: Apache-2.0
# ---

import marimo

__generated_with = "0.23.10"
app = marimo.App(width="full")


@app.cell
def _():
    import json
    import pathlib

    import marimo as mo
    import numpy as np
    import pandas as pd
    import umap
    from embedding_atlas.widget import EmbeddingAtlasWidget

    return EmbeddingAtlasWidget, json, mo, np, pathlib, pd, umap


@app.cell
def _(mo):
    mo.md(
        """
        # Embedding Atlas Visualization

        Loads the three embedding experiments, projects to 2D with UMAP, and opens an interactive Embedding Atlas widget per experiment.

        Color by `status`, `entity_type`, or `industry_division` in the Metadata panel.
        """
    )
    return


@app.cell
def _(mo):
    mo.md("## A: PCA Baseline — Raw Features")
    return


@app.cell
def _(
    EmbeddingAtlasWidget,
    json,
    mo,
    np,
    pathlib,
    pd,
    umap,
):
    output_dir = pathlib.Path("data/processed")

    path = output_dir / "embeddings_pca.json"
    with path.open() as f:
        data = json.load(f)
    df_pca = pd.DataFrame(data)
    dim_cols = [c for c in df_pca.columns if c.startswith("dim_")]
    dims = df_pca[dim_cols].to_numpy(dtype=np.float32)

    mo.output.append(mo.md(f"Loaded {len(df_pca)} points, {len(dim_cols)} dims. Projecting with UMAP..."))

    reducer = umap.UMAP(n_components=2, random_state=42, n_neighbors=30, min_dist=0.1)
    proj = reducer.fit_transform(dims)
    df_pca["projection_x"] = proj[:, 0]
    df_pca["projection_y"] = proj[:, 1]

    widget = EmbeddingAtlasWidget(df_pca, row_id="id", x="projection_x", y="projection_y", point_size=3.0)
    mo.output.append(mo.ui.anywidget(widget))
    return (output_dir, dim_cols, df_pca, reducer)


@app.cell
def _(mo):
    mo.md("## B: Random GNN — Untrained GraphSAGE")
    return


@app.cell
def _(
    EmbeddingAtlasWidget,
    json,
    mo,
    np,
    output_dir,
    pd,
    umap,
):
    path = output_dir / "embeddings_random.json"
    with path.open() as f:
        data = json.load(f)
    df_random = pd.DataFrame(data)
    dim_cols = [c for c in df_random.columns if c.startswith("dim_")]
    dims = df_random[dim_cols].to_numpy(dtype=np.float32)

    mo.output.append(mo.md(f"Loaded {len(df_random)} points, {len(dim_cols)} dims. Projecting with UMAP..."))

    reducer = umap.UMAP(n_components=2, random_state=42, n_neighbors=30, min_dist=0.1)
    proj = reducer.fit_transform(dims)
    df_random["projection_x"] = proj[:, 0]
    df_random["projection_y"] = proj[:, 1]

    widget = EmbeddingAtlasWidget(df_random, row_id="id", x="projection_x", y="projection_y", point_size=3.0)
    mo.output.append(mo.ui.anywidget(widget))
    return (df_random,)


@app.cell
def _(mo):
    mo.md("## C: Trained GNN — Link-Prediction Trained GraphSAGE")
    return


@app.cell
def _(
    EmbeddingAtlasWidget,
    json,
    mo,
    np,
    output_dir,
    pd,
    umap,
):
    path = output_dir / "embeddings_gnn.json"
    with path.open() as f:
        data = json.load(f)
    df_gnn = pd.DataFrame(data)
    dim_cols = [c for c in df_gnn.columns if c.startswith("dim_")]
    dims = df_gnn[dim_cols].to_numpy(dtype=np.float32)

    mo.output.append(mo.md(f"Loaded {len(df_gnn)} points, {len(dim_cols)} dims. Projecting with UMAP..."))

    reducer = umap.UMAP(n_components=2, random_state=42, n_neighbors=30, min_dist=0.1)
    proj = reducer.fit_transform(dims)
    df_gnn["projection_x"] = proj[:, 0]
    df_gnn["projection_y"] = proj[:, 1]

    widget = EmbeddingAtlasWidget(df_gnn, row_id="id", x="projection_x", y="projection_y", point_size=3.0)
    mo.output.append(mo.ui.anywidget(widget))
    return (df_gnn,)


@app.cell
def _(mo):
    mo.md(
        """
        ## Tips

        - **Color** = `status` (test signal) or `industry_division` (control) or `entity_type`
        - **A → B** = effect of adding graph topology to raw features
        - **B → C** = effect of link-prediction training on the representation
        - Switch between experiments and compare cluster boundaries
        - Select points in one widget and use them as a reference in another
        """
    )
    return
