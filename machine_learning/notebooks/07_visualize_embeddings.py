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
    mo.md("""
    # Embedding Atlas Visualization

    Loads the three embedding experiments, projects to 2D with UMAP, and opens an interactive Embedding Atlas widget per experiment.

    Color by `status`, `entity_type`, or `industry_division` in the Metadata panel.
    """)
    return


@app.cell
def _(pathlib):
    output_dir = pathlib.Path("data/processed")
    return (output_dir,)


@app.cell
def _(mo):
    mo.md("""
    ## A: PCA Baseline — Raw Features
    """)
    return


@app.cell
def _(EmbeddingAtlasWidget, json, mo, np, output_dir, pd, umap):
    pca_path = output_dir / "embeddings_pca.json"
    with pca_path.open() as pca_fh:
        pca_raw = json.load(pca_fh)
    pca_df = pd.DataFrame(pca_raw)
    pca_dcols = [c for c in pca_df.columns if c.startswith("dim_")]
    pca_arr = pca_df[pca_dcols].to_numpy(dtype=np.float32)

    pca_reducer = umap.UMAP(n_components=2, random_state=42, n_neighbors=30, min_dist=0.1)
    pca_xy = pca_reducer.fit_transform(pca_arr)
    pca_df["projection_x"] = pca_xy[:, 0]
    pca_df["projection_y"] = pca_xy[:, 1]

    pca_widget = EmbeddingAtlasWidget(pca_df, row_id="id", x="projection_x", y="projection_y", point_size=3.0)
    mo.output.append(mo.ui.anywidget(pca_widget))
    return


@app.cell
def _(mo):
    mo.md("""
    ## B: Random GNN — Untrained GraphSAGE
    """)
    return


@app.cell
def _(EmbeddingAtlasWidget, json, mo, np, output_dir, pd, umap):
    random_path = output_dir / "embeddings_random.json"
    with random_path.open() as random_fh:
        random_raw = json.load(random_fh)
    random_df = pd.DataFrame(random_raw)
    random_dcols = [c for c in random_df.columns if c.startswith("dim_")]
    random_arr = random_df[random_dcols].to_numpy(dtype=np.float32)

    random_reducer = umap.UMAP(n_components=2, random_state=42, n_neighbors=30, min_dist=0.1)
    random_xy = random_reducer.fit_transform(random_arr)
    random_df["projection_x"] = random_xy[:, 0]
    random_df["projection_y"] = random_xy[:, 1]

    random_widget = EmbeddingAtlasWidget(random_df, row_id="id", x="projection_x", y="projection_y", point_size=3.0)
    mo.output.append(mo.ui.anywidget(random_widget))
    return


@app.cell
def _(mo):
    mo.md("""
    ## C: Trained GNN — Link-Prediction Trained GraphSAGE
    """)
    return


@app.cell
def _(EmbeddingAtlasWidget, json, mo, np, output_dir, pd, umap):
    gnn_path = output_dir / "embeddings_gnn.json"
    with gnn_path.open() as gnn_fh:
        gnn_raw = json.load(gnn_fh)
    gnn_df = pd.DataFrame(gnn_raw)
    gnn_dcols = [c for c in gnn_df.columns if c.startswith("dim_")]
    gnn_arr = gnn_df[gnn_dcols].to_numpy(dtype=np.float32)

    gnn_reducer = umap.UMAP(n_components=2, random_state=42, n_neighbors=30, min_dist=0.1)
    gnn_xy = gnn_reducer.fit_transform(gnn_arr)
    gnn_df["projection_x"] = gnn_xy[:, 0]
    gnn_df["projection_y"] = gnn_xy[:, 1]

    gnn_widget = EmbeddingAtlasWidget(gnn_df, row_id="id", x="projection_x", y="projection_y", point_size=3.0)
    mo.output.append(mo.ui.anywidget(gnn_widget))
    return


@app.cell
def _(mo):
    mo.md("""
    ## Tips

    - **Color** = `status` (test signal) or `industry_division` (control) or `entity_type`
    - **A → B** = effect of adding graph topology to raw features
    - **B → C** = effect of link-prediction training on the representation
    - Switch between experiments and compare cluster boundaries
    - Select points in one widget and use them as a reference in another
    """)
    return


if __name__ == "__main__":
    app.run()
