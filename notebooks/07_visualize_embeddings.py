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
def _(mo):
    mo.md("""
    ## A: PCA Baseline — Raw Features
    """)
    return


@app.cell
def _(pathlib):
    output_dir = pathlib.Path("data/processed")
    return (output_dir,)


@app.cell
def _():
    def load_and_show(name: str, mo, EmbeddingAtlasWidget, json, np, pd, umap, output_dir):
        file_path = output_dir / f"embeddings_{name}.json"
        with file_path.open() as fh:
            raw = json.load(fh)
        df = pd.DataFrame(raw)
        dcols = [c for c in df.columns if c.startswith("dim_")]
        arr = df[dcols].to_numpy(dtype=np.float32)
        mo.output.append(mo.md(f"**{name}**: {len(df)} points, {len(dcols)} dims — projecting with UMAP..."))
        reducer = umap.UMAP(n_components=2, random_state=42, n_neighbors=30, min_dist=0.1)
        xy = reducer.fit_transform(arr)
        df["projection_x"] = xy[:, 0]
        df["projection_y"] = xy[:, 1]
        w = EmbeddingAtlasWidget(df, row_id="id", x="projection_x", y="projection_y", point_size=3.0)
        mo.output.append(mo.ui.anywidget(w))

    return (load_and_show,)


@app.cell
def _(mo):
    mo.md("""
    ## A: PCA Baseline — Raw Features
    """)
    return


@app.cell
def _(EmbeddingAtlasWidget, json, load_and_show, mo, np, output_dir, pd, umap):
    load_and_show("pca", mo, EmbeddingAtlasWidget, json, np, pd, umap, output_dir)
    return


@app.cell
def _(mo):
    mo.md("""
    ## B: Random GNN — Untrained GraphSAGE
    """)
    return


@app.cell
def _(EmbeddingAtlasWidget, json, load_and_show, mo, np, output_dir, pd, umap):
    load_and_show("random", mo, EmbeddingAtlasWidget, json, np, pd, umap, output_dir)
    return


@app.cell
def _(mo):
    mo.md("""
    ## C: Trained GNN — Link-Prediction Trained GraphSAGE
    """)
    return


@app.cell
def _(EmbeddingAtlasWidget, json, load_and_show, mo, np, output_dir, pd, umap):
    load_and_show("gnn", mo, EmbeddingAtlasWidget, json, np, pd, umap, output_dir)
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
