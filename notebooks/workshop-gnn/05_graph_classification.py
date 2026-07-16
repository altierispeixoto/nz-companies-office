# ---
# marimo-version: 0.23.9
# license: Apache-2.0
# ---

import marimo

__generated_with = "0.23.9"
app = marimo.App(width="full")


@app.cell
def _():
    import warnings

    import marimo as mo
    import matplotlib.pyplot as plt
    import networkx as nx
    import numpy as np
    import torch
    import torch.nn as nn
    import torch.nn.functional as F
    from torch_geometric.data import DataLoader
    from torch_geometric.datasets import TUDataset
    from torch_geometric.nn import GCNConv
    from torch_geometric.nn import global_add_pool
    from torch_geometric.nn import global_max_pool
    from torch_geometric.nn import global_mean_pool

    warnings.filterwarnings("ignore")
    return (
        DataLoader,
        F,
        GCNConv,
        TUDataset,
        global_add_pool,
        global_max_pool,
        global_mean_pool,
        mo,
        nn,
        nx,
        plt,
        torch,
    )


@app.cell
def _(mo):
    mo.md("""
    # GNN Workshop 5: Graph Classification & Pooling

    So far we've focused on **node-level** tasks (classifying individual nodes). But many real-world problems require **graph-level** predictions:

    - Is this molecule toxic or safe? (molecule classification)
    - Is this code snippet buggy? (program analysis)
    - What type of community is this? (social network analysis)

    ## The Challenge

    Node-level GNNs output a feature vector **per node**. To make a **graph-level** prediction, we need to combine all node features into a single representation.

    This is called **readout** or **pooling**.
    """)
    return


@app.cell
def _(mo):
    mo.md(r"""
    ## Global Pooling / Readout

    The simplest approach: aggregate all node features into one vector.

    ### Common Pooling Functions

    **Mean Pooling**: $$\mathbf{h}_G = \frac{1}{|V|} \sum_{v \in V} \mathbf{h}_v$$

    **Max Pooling**: $$\mathbf{h}_G = \max_{v \in V} \mathbf{h}_v$$ (element-wise)

    **Sum Pooling**: $$\mathbf{h}_G = \sum_{v \in V} \mathbf{h}_v$$

    > 💡 **Sum pooling** is often preferred because it can distinguish graph sizes (e.g., a molecule with 50 atoms vs 5 atoms should have different representations).

    ### The Complete Architecture

    ```
    Node Features → [GNN Layers] → Node Embeddings → [Pooling] → Graph Embedding → [MLP] → Prediction
    ```
    """)
    return


@app.cell
def _(DataLoader, TUDataset, mo):
    dataset = TUDataset(root="/tmp/TU", name="MUTAG")
    dataset = dataset.shuffle()

    train_dataset = dataset[:120]
    test_dataset = dataset[120:]

    train_loader = DataLoader(train_dataset, batch_size=32, shuffle=True)
    test_loader = DataLoader(test_dataset, batch_size=32)

    n_classes = dataset.num_classes
    n_features = dataset.num_node_features

    mo.md(
        f"""
        ## Dataset: MUTAG

        **MUTAG** is a dataset of 188 mutagenic molecules labeled by their mutagenicity.

        | Property | Value |
        |----------|-------|
        | Graphs | {len(dataset)} |
        | Classes | {n_classes} |
        | Node features | {n_features} |
        | Avg. nodes/graph | {dataset.data.x.shape[0] / len(dataset):.1f} |
        | Avg. edges/graph | {dataset.data.edge_index.shape[1] / len(dataset):.1f} |
        | Train | {len(train_dataset)} |
        | Test | {len(test_dataset)} |
        """
    )
    return dataset, n_classes, n_features, test_loader, train_loader


@app.cell
def _(dataset, mo, nx, plt):
    from torch_geometric.utils import to_networkx

    fig_mut, axes_mut = plt.subplots(2, 4, figsize=(20, 10))

    for _gi, ax in enumerate(axes_mut.flat):
        if _gi < len(dataset):
            data_i = dataset[_gi]
            G_i = to_networkx(data_i, to_undirected=True)
            color_map = plt.cm.Set2(data_i.x.argmax(dim=1).numpy() / max(1, data_i.x.shape[1] - 1))
            pos_i = nx.spring_layout(G_i, seed=_gi, k=2)
            nx.draw_networkx_nodes(G_i, pos_i, node_color=color_map, node_size=100, ax=ax)
            nx.draw_networkx_edges(G_i, pos_i, width=1, alpha=0.5, ax=ax)
            ax.set_title(f"Graph {_gi} (label: {data_i.y.item()})")
            ax.axis("off")

    plt.tight_layout()
    mo.mpl.interactive(plt.gcf())
    return


@app.cell
def _(F, GCNConv, global_mean_pool, mo, n_classes, n_features, nn, torch):
    class GraphClassifier(nn.Module):
        def __init__(self, in_dim, hidden_dim, out_dim):
            super().__init__()
            self.conv1 = GCNConv(in_dim, hidden_dim)
            self.conv2 = GCNConv(hidden_dim, hidden_dim)
            self.conv3 = GCNConv(hidden_dim, hidden_dim)
            self.lin = nn.Linear(hidden_dim, out_dim)

        def forward(self, x, edge_index, batch):
            x = F.relu(self.conv1(x, edge_index))
            x = F.relu(self.conv2(x, edge_index))
            x = F.relu(self.conv3(x, edge_index))
            x = global_mean_pool(x, batch)
            return F.log_softmax(self.lin(x), dim=1)

    model_gc = GraphClassifier(n_features, 64, n_classes)
    opt_gc = torch.optim.Adam(model_gc.parameters(), lr=0.005)

    mo.md(f"**Graph Classifier**: {sum(p.numel() for p in model_gc.parameters()):,} parameters")
    return model_gc, opt_gc


@app.cell
def _(F, mo, model_gc, opt_gc, test_loader, torch, train_loader):
    train_losses = []
    test_accs = []

    for _ep_gc in range(100):
        model_gc.train()
        total_loss = 0
        for _batch in train_loader:
            opt_gc.zero_grad()
            out_gc_tr = model_gc(_batch.x, _batch.edge_index, _batch.batch)
            loss_gc = F.nll_loss(out_gc_tr, _batch.y)
            loss_gc.backward()
            opt_gc.step()
            total_loss += loss_gc.item()
        train_losses.append(total_loss / len(train_loader))

        model_gc.eval()
        correct_gc = 0
        total_gc = 0
        with torch.no_grad():
            for _batch in test_loader:
                out_gc_ev = model_gc(_batch.x, _batch.edge_index, _batch.batch)
                pred_gc = out_gc_ev.argmax(dim=1)
                correct_gc += (pred_gc == _batch.y).sum().item()
                total_gc += _batch.y.size(0)
        test_accs.append(correct_gc / total_gc)

        if (_ep_gc + 1) % 20 == 0:
            mo.output.append(
                mo.md(f"Epoch {_ep_gc + 1:3d}/100 | Loss: {train_losses[-1]:.4f} | Test Acc: {test_accs[-1]:.2%}")
            )

    mo.md(f"**Final Test Accuracy**: {test_accs[-1]:.2%}")
    return test_accs, train_losses


@app.cell
def _(mo, plt, test_accs, train_losses):
    fig_gc, (ax_l, ax_a) = plt.subplots(1, 2, figsize=(14, 5))

    ax_l.plot(train_losses, color="steelblue", linewidth=2)
    ax_l.set_xlabel("Epoch")
    ax_l.set_ylabel("Loss")
    ax_l.set_title("Training Loss")
    ax_l.grid(alpha=0.3)

    ax_a.plot(test_accs, color="#2b8a3e", linewidth=2)
    ax_a.set_xlabel("Epoch")
    ax_a.set_ylabel("Test Accuracy")
    ax_a.set_title("Graph Classification Accuracy")
    ax_a.grid(alpha=0.3)

    plt.tight_layout()
    mo.mpl.interactive(plt.gcf())
    return


@app.cell
def _(mo):
    mo.md("""
    ## Comparing Pooling Strategies

    How does the choice of pooling affect performance?
    """)
    return


@app.cell
def _(
    F,
    GCNConv,
    global_add_pool,
    global_max_pool,
    global_mean_pool,
    n_classes,
    n_features,
    nn,
    test_loader,
    torch,
    train_loader,
):
    class ComparePooling(nn.Module):
        def __init__(self, in_dim, hidden_dim, out_dim, pool="mean"):
            super().__init__()
            self.conv1 = GCNConv(in_dim, hidden_dim)
            self.conv2 = GCNConv(hidden_dim, hidden_dim)
            self.lin = nn.Linear(hidden_dim, out_dim)
            self.pool = pool

        def forward(self, x, edge_index, batch):
            x = F.relu(self.conv1(x, edge_index))
            x = F.relu(self.conv2(x, edge_index))
            if self.pool == "mean":
                x = global_mean_pool(x, batch)
            elif self.pool == "max":
                x = global_max_pool(x, batch)
            else:
                x = global_add_pool(x, batch)
            return F.log_softmax(self.lin(x), dim=1)

    results_pool = {}
    for pool_name in ["mean", "max", "sum"]:
        model_c = ComparePooling(n_features, 64, n_classes, pool_name)
        opt_c = torch.optim.Adam(model_c.parameters(), lr=0.005)
        for _ in range(50):
            model_c.train()
            for _batch_p in train_loader:
                opt_c.zero_grad()
                out_p = model_c(_batch_p.x, _batch_p.edge_index, _batch_p.batch)
                F.nll_loss(out_p, _batch_p.y).backward()
                opt_c.step()
        model_c.eval()
        correct_c = 0
        total_c = 0
        with torch.no_grad():
            for _batch_p in test_loader:
                out_p = model_c(_batch_p.x, _batch_p.edge_index, _batch_p.batch)
                correct_c += (out_p.argmax(dim=1) == _batch_p.y).sum().item()
                total_c += _batch_p.y.size(0)
        results_pool[pool_name] = correct_c / total_c
    return (results_pool,)


@app.cell
def _(mo, plt, results_pool):
    fig_pool, ax_pool = plt.subplots(figsize=(8, 5))
    names = list(results_pool.keys())
    scores = list(results_pool.values())
    colors_pool = ["#339af0", "#e03131", "#2b8a3e"]
    bars = ax_pool.bar(names, scores, color=colors_pool, width=0.5)
    ax_pool.set_ylabel("Test Accuracy")
    ax_pool.set_title("Pooling Strategy Comparison")
    ax_pool.set_ylim(0, 1)
    for bar, score in zip(bars, scores):
        ax_pool.text(
            bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.01, f"{score:.1%}", ha="center", fontweight="bold"
        )
    ax_pool.grid(alpha=0.3, axis="y")
    plt.tight_layout()
    mo.mpl.interactive(plt.gcf())
    return


@app.cell
def _(mo):
    mo.md(r"""
    ## Hierarchical Pooling

    Global pooling discards all graph structure. **Hierarchical pooling** progressively coarsens the graph:

    1. Start with the original graph
    2. Cluster nodes and pool them into super-nodes
    3. Repeat

    This creates a **graph of graphs** — preserving hierarchical structure.

    ### DiffPool (Ying et al., 2018)
    Learns a **soft cluster assignment** matrix \(S\):

    $$S^{(k)} = \text{softmax}(\text{GNN}^{(k)}(A^{(k)}, X^{(k)}))$$

    Then pools:
    $$X^{(k+1)} = (S^{(k)})^T X^{(k)}$$
    $$A^{(k+1)} = (S^{(k)})^T A^{(k)} S^{(k)}$$

    ### TopKPool (Gao & Ji, 2019)
    Simple and efficient: project node features to a score, keep the top-\(k\) nodes, discard the rest.
    """)
    return


@app.cell
def _(mo):
    mo.md("""
    ## When to Use Which Pooling?

    | Pooling | When to Use |
    |---------|-------------|
    | **Global Mean** | Simple baseline, graphs of similar sizes |
    | **Global Sum** | Graph size matters (e.g., molecule with more atoms = different properties) |
    | **Global Max** | Only the most salient feature matters |
    | **DiffPool** | Hierarchical structure is important, you have enough data |
    | **TopKPool** | You want to keep important nodes and discard noise |

    ## Beyond Classification: Other Graph-Level Tasks

    - **Graph regression**: Predicting a continuous value (e.g., molecular energy)
    - **Graph generation**: Creating new graphs (e.g., drug discovery)
    - **Graph matching**: Comparing two graphs (e.g., shape matching)
    - **Anomaly detection**: Finding unusual graphs (e.g., fraud detection)

    ## Summary

    ✅ **Graph-level tasks** require pooling node embeddings into a single graph representation
    ✅ **Global pooling** options: mean, max, sum — each has different properties
    ✅ **Hierarchical pooling** preserves structure while coarsening
    ✅ PyTorch Geometric supports `global_mean_pool`, `global_max_pool`, `global_add_pool`
    ✅ Graph classification enables applications in drug discovery, materials science, and more

    **Next up:** Advanced topics — link prediction, explainability, and real-world deployment!
    """)
    return


if __name__ == "__main__":
    app.run()
