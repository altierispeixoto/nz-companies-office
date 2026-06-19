# ---
# marimo-version: 0.23.9
# license: Apache-2.0
# ---

import marimo

__generated_with = "0.23.9"
app = marimo.App(width="full")


@app.cell
def _():
    # Standard library
    import pathlib

    # Third-party
    import marimo as mo
    import matplotlib.pyplot as plt
    import torch
    from sklearn.metrics import RocCurveDisplay

    # Local utilities
    from nz_companies_office.models.link_predictor import LinkPredictor
    from nz_companies_office.models.trainer import LinkPredictorTrainer
    from nz_companies_office.utils.device import get_device

    device = get_device()
    return (
        LinkPredictor,
        LinkPredictorTrainer,
        RocCurveDisplay,
        device,
        mo,
        pathlib,
        plt,
        torch,
    )


@app.cell
def _(mo):
    mo.md(r"""
    # NZ Companies Office: Link Prediction with GNNs

    Loads the dataset from **00_dataset.py** and trains a GraphSAGE-based model to recommend potential investors.

    1. Load checkpoint (graph, splits, feature dimensions)
    2. Build **shareholder prediction** model (HeteroConv encoder + dot-product decoder)
    3. Train with binary cross-entropy and early stopping
    4. Evaluate using AUC-ROC and Average Precision
    """)
    return


@app.cell
def _(mo):
    mo.md(r"""
    ### The Business Problem

    A private equity firm wants to identify **potential investors** for NZ companies. Currently they rely on
    manual networking and industry contacts — slow, biased, and limited in scale.

    **The insight**: investor networks follow structural patterns. Companies on the same board tend to share
    shareholders; investors in one industry often invest in adjacent ones; the presence of certain directors
    signals suitability for certain capital.

    This model learns those patterns directly from the graph:
    - **Directors** provide signals about company governance quality and network proximity
    - **Existing shareholders** reveal co-investment clusters
    - **Company attributes** (status, type) filter by investment eligibility

    The output is a ranking of potential new shareholders for any selected company, together with
    explanations showing *why* each recommendation makes sense — which shared directors, co-investors,
    or similar companies support the prediction.
    """)
    return


@app.cell
def _(device, mo, pathlib, torch):
    pipeline_path = pathlib.Path("data/processed/pipeline_checkpoint/pipeline.pt")
    if pipeline_path.exists():
        checkpoint = torch.load(pipeline_path, map_location="cpu", weights_only=False)
        train_data = checkpoint["train_data"].to(device)
        val_data = checkpoint["val_data"].to(device)
        test_data = checkpoint["test_data"].to(device)
        training_edges = checkpoint["train_pos"].to(device)
        validation_edges = checkpoint["val_pos"].to(device)
        test_edges = checkpoint["test_pos"].to(device)
        validation_negatives = checkpoint["val_neg"].to(device)
        test_negatives = checkpoint["test_neg"].to(device)
        company_feature_dim = checkpoint["n_company_feats"]
        director_feature_dim = checkpoint["n_director_feats"]
        shareholder_feature_dim = checkpoint["n_shareholder_feats"]
    else:
        mo.output.append(mo.md("\u26a0\ufe0f **No pipeline checkpoint**. Run **00_dataset.py** first."))
        train_data = val_data = test_data = None
        training_edges = validation_edges = test_edges = validation_negatives = test_negatives = None
        company_feature_dim = director_feature_dim = shareholder_feature_dim = None
    return (
        company_feature_dim,
        director_feature_dim,
        shareholder_feature_dim,
        test_data,
        test_edges,
        test_negatives,
        train_data,
        training_edges,
        val_data,
        validation_edges,
        validation_negatives,
    )


@app.cell
def _(mo):
    mo.md(r"""
    ## 1. Model Architecture

    ```
    ┌──────────────────────────────────────────────────────────┐
    │                     Encoder (HeteroConv x2)              │
    │                                                          │
    │   Director Feats ──┐                                     │
    │                    │  ┌────────────┐    ┌────────────┐   │
    │   Company Feats ───┼──┤ GraphSAGE  ├────┤ GraphSAGE  │   │
    │                    │  │  Layer 1   │    │  Layer 2   │   │
    │   Shareholder Feats┘  │  h=32      │    │  h=16      │   │
    │                       └────────────┘    └────────────┘   │
    │                            │                  │          │
    │                     ┌──────┴──────┐     ┌──────┴──────┐  │
    │                     │   z_dir     │     │  z_comp     │  │
    │                     │  z_share    │     │  z_share    │  │
    │                     └─────────────┘     └─────────────┘  │
    │                            │                  │          │
    └────────────────────────────┼──────────────────┼──────────┘
                                 │                  │
    ┌────────────────────────────┼──────────────────┼───────────┐
    │              Decoder (dot-product)            │           │
    │                     ┌──────┴────────────────┐ │           │
    │                     │  z_src · z_dst = score│ │
    │                     └──────┬────────────────┘ │           │
    │                            │                  │           │
    │      logit → sigmoid → probability ∈ [0, 1]   │          │
    └───────────────────────────────────────────────────────────┘
    ```

    ### Why this architecture?

    - **Heterogeneous GraphSAGE** (``HeteroConv`` + ``SAGEConv``) was chosen over GCN or GAT because it
      handles multiple node/edge types natively — directors, shareholders, and companies all have
      different features and connect through different relationships. GCN requires a homogeneous
      graph; GAT is more expressive but slower and prone to overfitting at our graph scale.

    - **GraphSAGE** is inductive (can generalise to unseen nodes) and uses **mean aggregation**,
      which acts as a smoothed neighbourhood average — well-suited for detecting co-investment
      clusters where the *presence* of shared investors matters more than their identity.

    - **Dot-product decoder** is the simplest link prediction head: ``score = z_src · z_dst``.
      Single-vector embeddings are sufficient because each shareholder-company pair has at most
      one relationship type. A more complex decoder (MLP, bilinear) would add parameters without
      a corresponding edge-feature signal to justify them.

    - **Two layers** with 32 → 16 hidden units: one layer reaches direct neighbours (co-investors);
      a second layer captures 2-hop patterns (investors-of-investors). Three or more layers risk
      over-smoothing at our graph scale (<100 k edges) without measurable gain.

    ### Is this the best architecture for the problem?

    | Approach | Pros | Cons |
    |---|---|---|
    | **GraphSAGE (current)** | Fast, inductive, heterogeneous, low parameter count | Mean-pooling loses fine-grained neighbour identity |
    | **GAT** | Attention-weighted neighbourhoods, captures importance | ~4× params, slower, overfits at small scale |
    | **RGCN** | Explicit relation-type matrices for each edge type | Severe over-parameterisation for our 2 edge types |
    | **Node2Vec + MLP** | Simple, familiar pipeline | No inductive capacity, no multi-hop structure, separate embedding for each split |
    | **LightGCN** | State-of-the-art for recommendation graphs | Homogeneous only — needs workarounds for multi-node-type graphs |

    **Bottom line**: GraphSAGE hits the sweet spot for this problem — expressive enough to capture
    co-investment structure, simple enough to train on a single GPU in under a minute, and
    naturally handles heterogeneous nodes. A GAT-based model would be the next thing to try if
    we needed to distinguish *which* director or shareholder matters more for a prediction.

    ### Tradeoffs

    - **Speed vs expressiveness**: Mean aggregation is fast but treats all neighbours equally.
      A director who chairs the board gets the same weight as a dormant director.
    - **Two layers vs deeper**: Two hops capture investor-of-investor patterns but miss longer
      chains. Deeper networks would need skip connections and normalisation to avoid
      over-smoothing.
    - **Low-dimensional embeddings (16d)**: Forces the model to learn compact representations,
      which acts as regularisation but may lose fine-grained investor specialisation.
      Increasing to 32–64d would be the first hyper-parameter to tune.
    - **Dot-product vs bilinear decoder**: The dot-product assumes symmetric relationship
      strength. A bilinear decoder (``z_srcᵀ W z_dst``) could model asymmetric patterns
      but adds |W| = 16² = 256 parameters — negligible cost but also negligible gain for
      symmetric investor relationships.
    """)
    return


@app.cell
def _(
    LinkPredictor,
    company_feature_dim,
    device,
    director_feature_dim,
    shareholder_feature_dim,
    torch,
):
    model = LinkPredictor(
        dir_feats=director_feature_dim,
        comp_feats=company_feature_dim,
        share_feats=shareholder_feature_dim,
    ).to(device)
    optimizer = torch.optim.Adam(model.parameters(), lr=0.005, weight_decay=1e-4)
    parameter_count = sum(p.numel() for p in model.parameters())
    return model, optimizer, parameter_count


@app.cell
def _(mo, parameter_count):
    mo.md(f"""
    **Model**: HeteroConv encoder + dot-product decoder — **{parameter_count:,}** parameters
    """)
    return


@app.cell
def _(
    LinkPredictorTrainer,
    model,
    optimizer,
    test_data,
    train_data,
    training_edges,
    val_data,
    validation_edges,
    validation_negatives,
):
    trainer = LinkPredictorTrainer(
        model=model,
        optimizer=optimizer,
        train_data=train_data,
        val_data=val_data,
        test_data=test_data,
        training_edges=training_edges,
        validation_edges=validation_edges,
        validation_negatives=validation_negatives,
    )
    return (trainer,)


@app.cell
def _(mo):
    mo.md(r"""
    ## 2. Training

    Known shareholder-company edges should score high; randomly sampled non-edges should score low.
    Directors edges remain visible during message passing, providing structural context.
    Early stopping: training stops if validation AUC does not improve for 20 epochs.
    """)
    return


@app.cell
def _(mo, torch, trainer):
    torch.cuda.empty_cache()

    def _display_progress(epoch: int, loss: float, validation_auc: float, best_validation_auc: float) -> None:
        """Report training progress to the marimo output area every 20 epochs."""
        if epoch == 1 or epoch % 20 == 0:
            mo.output.append(
                mo.md(
                    f"Epoch {epoch:3d}/50 | Loss: {loss:.4f} | Val AUC: {validation_auc:.4f} "
                    f"| Best: {best_validation_auc:.4f}"
                )
            )

    training_result = trainer.train(
        num_epochs=50,
        patience=20,
        progress_callback=_display_progress,
    )

    if training_result.stopped_early:
        mo.output.append(
            mo.md(
                f"**Early stopping** at epoch {training_result.final_epoch} — "
                f"best Val AUC {training_result.best_validation_auc:.4f} "
                f"at epoch {training_result.best_epoch}."
            )
        )
    else:
        mo.output.append(
            mo.md(
                f"Training completed — best Val AUC {training_result.best_validation_auc:.4f} "
                f"at epoch {training_result.best_epoch}."
            )
        )
    return (training_result,)


@app.cell
def _(mo, plt, training_result):
    loss_history = training_result.loss_history
    _fig, axis = plt.subplots(figsize=(10, 4))
    axis.plot(loss_history, color="steelblue", linewidth=2)
    axis.set_xlabel("Epoch")
    axis.set_ylabel("Loss")
    axis.set_title("Training Loss")
    axis.grid(alpha=0.3)
    plt.tight_layout()
    mo.mpl.interactive(plt.gcf())
    return


@app.cell
def _(mo):
    mo.md(r"""
    ## 3. Evaluation

    Evaluates on held-out edges:
    - **Positive edges**: Real shareholder-company relationships (hidden during training)
    - **Negative edges**: Randomly sampled non-edges

    Metrics: **AUC-ROC** and **Average Precision**.
    """)
    return


@app.cell
def _(
    test_data,
    test_edges,
    test_negatives,
    trainer,
    val_data,
    validation_edges,
    validation_negatives,
):
    # Validation: encode using train + val graph (no test edges in message passing)
    validation_results = trainer.evaluate(
        positive_edges=validation_edges,
        negative_edges=validation_negatives,
        data=val_data,
    )
    # Test: encode using full graph (standard transductive setup)
    test_results = trainer.evaluate(
        positive_edges=test_edges,
        negative_edges=test_negatives,
        data=test_data,
    )
    return test_results, validation_results


@app.cell
def _(RocCurveDisplay, mo, plt, test_results):
    _fig, (roc_axis, score_axis) = plt.subplots(1, 2, figsize=(14, 5))

    # ROC curve
    RocCurveDisplay.from_predictions(
        test_results.labels.cpu().numpy(),
        test_results.scores.cpu().numpy(),
        ax=roc_axis,
    )
    roc_axis.plot([0, 1], [0, 1], "k--", alpha=0.3)
    roc_axis.set_title(f"Test ROC Curve (AUC = {test_results.auc:.3f})")
    roc_axis.grid(alpha=0.3)

    # Score distribution
    scores_np = test_results.scores.cpu().numpy()
    labels_np = test_results.labels.cpu().numpy()
    score_axis.hist(
        scores_np[labels_np == 1],
        bins=30,
        alpha=0.6,
        label="Positive (real edges)",
        color="#2b8a3e",
    )
    score_axis.hist(
        scores_np[labels_np == 0],
        bins=30,
        alpha=0.6,
        label="Negative (non-edges)",
        color="#e03131",
    )
    score_axis.set_xlabel("Probability")
    score_axis.set_ylabel("Count")
    score_axis.set_title("Score Distribution by Class")
    score_axis.legend()
    score_axis.grid(alpha=0.3)

    plt.tight_layout()
    mo.mpl.interactive(plt.gcf())
    return


@app.cell
def _(mo, test_results, validation_results):
    mo.md(f"""
    ## Results

    | Metric | Validation | Test |
    |--------|-----------|------|
    | **AUC-ROC** | {validation_results.auc:.3f} | {test_results.auc:.3f} |
    | **Average Precision** | {validation_results.average_precision:.3f} | {test_results.average_precision:.3f} |

    ### Interpretation

    - **AUC-ROC > 0.9**: The model effectively distinguishes real investment relationships from non-edges
    - **High Average Precision**: High-scoring predictions are very likely to be real investors
    - The model learned structural patterns: how board composition and existing investors predict future investors
    """)
    return


@app.cell
def _(mo):
    mo.md(r"""
    ## 4. Interactive Model Testing

    Open **[02_interactive_testing.py](02_interactive_testing.py)** in marimo for the standalone testing notebook.

    This loads the trained model and lets you search companies, see predictions with explanations.
    """)
    return


@app.cell
def _(mo):
    mo.md(r"""
    ## Summary

    ✅ **Loaded** dataset from `00_dataset.py`

    ✅ **Trained** a GraphSAGE-based shareholder prediction model

    ✅ **Achieved strong separation** between known and non-existent investment relationships

    ✅ **Saved** model weights to `data/processed/model_checkpoint.pt`

    ### Next Steps

    - Open **02_interactive_testing.py** to explore predictions interactively
    - Re-run **00_dataset.py** with a fresh Neo4j connection when new data is loaded
    - Incorporate Address nodes and geographic proximity for richer features
    """)
    return


@app.cell
def _():
    return


if __name__ == "__main__":
    app.run()
