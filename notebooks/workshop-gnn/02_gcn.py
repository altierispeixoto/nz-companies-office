# ---
# marimo-version: 0.23.9
# license: Apache-2.0
# ---

import marimo

__generated_with = "0.23.9"
app = marimo.App(width="full")


@app.cell
def _():
    import torch
    import torch.nn as nn
    import torch.nn.functional as F
    import numpy as np
    import networkx as nx
    import matplotlib.pyplot as plt
    import marimo as mo
    from torch_geometric.nn import GCNConv
    from torch_geometric.datasets import Planetoid
    from torch_geometric.utils import to_networkx, degree
    import warnings
    warnings.filterwarnings("ignore")
    return F, GCNConv, Planetoid, mo, nn, np, nx, plt, to_networkx, torch


@app.cell
def _(mo):
    mo.md(r"""
    # GNN Workshop 2: Graph Convolutional Networks (GCN)

    The **Graph Convolutional Network** (Kipf & Welling, 2017) is the most influential GNN architecture. It introduced a simple yet effective way to generalize convolution to graphs.

    ## From CNNs to GCNs

    In a **CNN**, each pixel's output is a weighted sum of its neighbors (the kernel window). In a **GCN**, each node's output is a normalized sum of its neighbors' features.

    ### The GCN Layer Formula

    $$H^{(k+1)} = \sigma\left(\hat{D}^{-1/2} \hat{A} \hat{D}^{-1/2} H^{(k)} W^{(k)}
    \right)$$

    Where:
    - \(\hat{A} = A + I\) — adjacency matrix with self-loops
    - \(\hat{D}_{ii} = \sum_j \hat{A}_{ij}\) — degree matrix of \(\hat{A}\)
    - \(H^{(k)}\) — node features at layer \(k\)
    - \(W^{(k)}\) — learnable weight matrix
    - \(\sigma\) — activation function (ReLU)

    The normalization \(\hat{D}^{-1/2} \hat{A} \hat{D}^{-1/2}\) prevents the scale of features from growing with node degree.
    """)
    return


@app.cell
def _(mo):
    mo.md("""
    ## Setting Up: The Cora Dataset

    We'll use the **Cora citation network** — a classic benchmark for GNNs:
    - **Nodes**: Scientific papers
    - **Edges**: Citation links (paper A cites paper B)
    - **Features**: Bag-of-words representation of each paper
    - **Labels**: Research topic (one of 7 classes)

    | Property | Value |
    |----------|-------|
    | Nodes | 2,708 |
    | Edges | 10,556 |
    | Features per node | 1,433 |
    | Classes | 7 |
    """)
    return


@app.cell
def _(Planetoid, mo):
    dataset = Planetoid(root="/tmp/Cora", name="Cora")
    data = dataset[0]

    mo.md(
        f"""
        Downloaded Cora dataset:
        - **Nodes**: {data.x.shape[0]}
        - **Features**: {data.x.shape[1]}
        - **Edges**: {data.edge_index.shape[1]}
        - **Classes**: {dataset.num_classes}
        - **Training nodes**: {data.train_mask.sum().item()}
        - **Validation nodes**: {data.val_mask.sum().item()}
        - **Test nodes**: {data.test_mask.sum().item()}
        """
    )
    return (data,)


@app.cell
def _(data, mo, np, nx, plt, to_networkx):
    G_cora = to_networkx(data, to_undirected=True)

    fig_cora, (ax_hist, ax_net) = plt.subplots(1, 2, figsize=(16, 6))

    degrees = [d for _, d in G_cora.degree()]
    ax_hist.hist(degrees, bins=50, color="steelblue", edgecolor="white", alpha=0.7)
    ax_hist.set_xlabel("Degree")
    ax_hist.set_ylabel("Frequency")
    ax_hist.set_title(f"Cora Degree Distribution (avg: {np.mean(degrees):.1f})")
    ax_hist.axvline(np.mean(degrees), color="red", linestyle="--", label=f"Mean: {np.mean(degrees):.1f}")
    ax_hist.legend()

    pos_cora = nx.spring_layout(G_cora, seed=42, iterations=30)
    labels_cora = data.y.numpy()
    cmap_cora = plt.cm.tab10
    node_colors_cora = [cmap_cora(labels_cora[i] / 7) for i in range(len(G_cora.nodes()))]
    nx.draw_networkx_nodes(G_cora, pos_cora, node_color=node_colors_cora, node_size=10, alpha=0.7, ax=ax_net)
    ax_net.set_title("Cora Citation Network (colored by topic)")
    ax_net.axis("off")

    plt.tight_layout()
    mo.mpl.interactive(plt.gcf())
    return


@app.cell
def _(mo):
    mo.md(r"""
    ## Building a 2-Layer GCN

    The classic GCN for node classification:

    $$Z = \text{softmax}\left(\hat{A} \cdot \text{ReLU}\left(\hat{A} \cdot X W^{(0)}
    \right) \cdot W^{(1)}
    \right)$$

    Two layers = 2-hop neighborhood in the final representation.
    """)
    return


@app.cell
def _(F, GCNConv, nn):
    class GCN(nn.Module):
        def __init__(self, in_dim, hidden_dim, out_dim, dropout=0.5):
            super().__init__()
            self.conv1 = GCNConv(in_dim, hidden_dim)
            self.conv2 = GCNConv(hidden_dim, out_dim)
            self.dropout = dropout

        def forward(self, x, edge_index):
            x = self.conv1(x, edge_index)
            x = F.relu(x)
            x = F.dropout(x, p=self.dropout, training=self.training)
            x = self.conv2(x, edge_index)
            return F.log_softmax(x, dim=1)

    return (GCN,)


@app.cell
def _(GCN, data, mo, torch):
    in_dim = data.x.shape[1]
    hidden_dim = 16
    out_dim = 7

    model_gcn = GCN(in_dim, hidden_dim, out_dim)
    optimizer_gcn = torch.optim.Adam(model_gcn.parameters(), lr=0.01, weight_decay=5e-4)

    mo.md(f"**Model**: {in_dim} → {hidden_dim} → {out_dim} (GCN with {sum(p.numel() for p in model_gcn.parameters())} parameters)")
    return model_gcn, optimizer_gcn


@app.cell
def _(data, mo, model_gcn):
    out_gcn = model_gcn(data.x, data.edge_index)
    pred_init = out_gcn.argmax(dim=1)
    acc_init = (pred_init[data.test_mask] == data.y[data.test_mask]).float().mean()

    mo.md(f"**Random initialization test accuracy**: {acc_init:.1%} (should be ~{1/7:.1%} for 7 classes)")
    return


@app.cell
def _(F, data, mo, model_gcn, optimizer_gcn, torch):
    loss_history = []
    acc_history = []

    for epoch in range(200):
        model_gcn.train()
        optimizer_gcn.zero_grad()
        out = model_gcn(data.x, data.edge_index)
        loss = F.nll_loss(out[data.train_mask], data.y[data.train_mask])
        loss.backward()
        optimizer_gcn.step()

        model_gcn.eval()
        with torch.no_grad():
            pred = out.argmax(dim=1)
            val_acc = (pred[data.val_mask] == data.y[data.val_mask]).float().mean()
            train_acc = (pred[data.train_mask] == data.y[data.train_mask]).float().mean()

        loss_history.append(loss.item())
        acc_history.append(train_acc.item())

        if (epoch + 1) % 50 == 0:
            mo.output.append(mo.md(f"Epoch {epoch + 1:3d}/200 | Loss: {loss.item():.4f} | Train Acc: {train_acc:.3f} | Val Acc: {val_acc:.3f}"))

    mo.md("Training complete!")
    return acc_history, loss_history


@app.cell
def _(acc_history, data, loss_history, mo, model_gcn, plt, torch):
    fig_train, (ax_loss, ax_acc) = plt.subplots(1, 2, figsize=(14, 5))

    ax_loss.plot(loss_history, color="steelblue", linewidth=2)
    ax_loss.set_xlabel("Epoch")
    ax_loss.set_ylabel("Loss")
    ax_loss.set_title("Training Loss")
    ax_loss.grid(alpha=0.3)

    ax_acc.plot(acc_history, color="#2b8a3e", linewidth=2)
    ax_acc.set_xlabel("Epoch")
    ax_acc.set_ylabel("Accuracy")
    ax_acc.set_title("Training Accuracy")
    ax_acc.grid(alpha=0.3)

    plt.tight_layout()
    mo.mpl.interactive(plt.gcf())

    model_gcn.eval()
    with torch.no_grad():
        out_eval = model_gcn(data.x, data.edge_index)
        pred_eval = out_eval.argmax(dim=1)
        test_acc = (pred_eval[data.test_mask] == data.y[data.test_mask]).float().mean()

    mo.md(f"**Final Test Accuracy**: {test_acc:.2%}")
    return


@app.cell
def _(mo):
    mo.md("""
    ## Visualizing GCN Predictions

    Let's see how the GCN's learned embeddings look in 2D:
    """)
    return


@app.cell
def _(data, mo, model_gcn, plt, torch):
    from sklearn.manifold import TSNE

    model_gcn.eval()
    with torch.no_grad():
        embeddings = model_gcn.conv1(data.x, data.edge_index).numpy()

    tsne = TSNE(n_components=2, random_state=42, perplexity=30)
    emb_2d = tsne.fit_transform(embeddings)

    fig_tsne, ax_tsne = plt.subplots(figsize=(10, 8))
    colors_tsne = plt.cm.tab10(data.y.numpy() / 7)
    scatter = ax_tsne.scatter(emb_2d[:, 0], emb_2d[:, 1], c=colors_tsne, s=20, alpha=0.7)

    ax_tsne.set_title("GCN Layer 1 Embeddings (t-SNE projection)", fontsize=14)
    ax_tsne.set_xlabel("t-SNE dim 1")
    ax_tsne.set_ylabel("t-SNE dim 2")
    plt.tight_layout()
    mo.mpl.interactive(plt.gcf())
    return


@app.cell
def _(mo):
    mo.md("""
    ## GCN vs MLP: Why the Graph Matters

    To understand why GCNs are powerful, let's compare with a simple MLP that ignores graph structure entirely.
    """)
    return


@app.cell
def _(F, data, mo, model_gcn, nn, torch):
    class MLP(nn.Module):
        def __init__(self, in_dim, hidden_dim, out_dim, dropout=0.5):
            super().__init__()
            self.lin1 = nn.Linear(in_dim, hidden_dim)
            self.lin2 = nn.Linear(hidden_dim, out_dim)
            self.dropout = dropout

        def forward(self, x):
            x = F.relu(self.lin1(x))
            x = F.dropout(x, p=self.dropout, training=self.training)
            return F.log_softmax(self.lin2(x), dim=1)

    mlp = MLP(data.x.shape[1], 16, 7)
    opt_mlp = torch.optim.Adam(mlp.parameters(), lr=0.01, weight_decay=5e-4)

    mlp_loss = []
    mlp_acc = []
    for _ep in range(200):
        mlp.train()
        opt_mlp.zero_grad()
        out_mlp = mlp(data.x)
        l_mlp = F.nll_loss(out_mlp[data.train_mask], data.y[data.train_mask])
        l_mlp.backward()
        opt_mlp.step()

        mlp.eval()
        pred_mlp = out_mlp.argmax(dim=1)
        train_acc_mlp = (pred_mlp[data.train_mask] == data.y[data.train_mask]).float().mean()
        mlp_loss.append(l_mlp.item())
        mlp_acc.append(train_acc_mlp.item())

    mlp.eval()
    test_acc_mlp = (pred_mlp[data.test_mask] == data.y[data.test_mask]).float().mean()

    model_gcn.eval()
    with torch.no_grad():
        gcn_eval_out = model_gcn(data.x, data.edge_index)
        gcn_test_acc = (gcn_eval_out.argmax(dim=1)[data.test_mask] == data.y[data.test_mask]).float().mean()

    mo.md(
        f"""
        | Model | Test Accuracy |
        |-------|:------------:|
        | **MLP** (no graph structure) | {test_acc_mlp:.2%} |
        | **GCN** (uses graph structure) | {gcn_test_acc:.2%} |
        | **Improvement** | **{gcn_test_acc - test_acc_mlp:+.2%}** |

        The GCN outperforms the MLP because it leverages the **graph structure** — papers that cite each other tend to be about similar topics!
        """
    )
    return gcn_test_acc, mlp_acc, test_acc_mlp


@app.cell
def _(acc_history, gcn_test_acc, mlp_acc, mo, plt, test_acc_mlp):
    fig_compare, (ax_c1, ax_c2) = plt.subplots(1, 2, figsize=(14, 5))

    ax_c1.bar(["MLP", "GCN"], [test_acc_mlp, gcn_test_acc], color=["#ffa94d", "#339af0"], width=0.5)
    ax_c1.set_ylabel("Test Accuracy")
    ax_c1.set_title("MLP vs GCN on Cora")
    ax_c1.set_ylim(0, 1)
    for _i, _v in enumerate([test_acc_mlp, gcn_test_acc]):
        ax_c1.text(_i, _v + 0.02, f"{_v:.1%}", ha="center", fontweight="bold")
    ax_c1.grid(alpha=0.3, axis="y")

    ax_c2.plot(mlp_acc, color="#ffa94d", linewidth=2, label="MLP")
    ax_c2.plot(acc_history, color="#339af0", linewidth=2, label="GCN")
    ax_c2.set_xlabel("Epoch")
    ax_c2.set_ylabel("Training Accuracy")
    ax_c2.set_title("Training Comparison")
    ax_c2.legend()
    ax_c2.grid(alpha=0.3)

    plt.tight_layout()
    mo.mpl.interactive(plt.gcf())
    return


@app.cell
def _(mo):
    mo.md("""
    ## Why Does the GCN Work Better?

    The GCN's secret sauce is the **graph structure** — it acts as a **smoothing prior**:

    1. **Homophily**: In citation networks, papers that cite each other tend to be about similar topics
    2. **Feature smoothing**: The GCN averages features across connected nodes, reducing noise
    3. **Information flow**: Labels propagate from labeled to unlabeled nodes through the graph

    The MLP sees each paper in isolation — it only has the bag-of-words features. The GCN also sees **who cites whom**, giving it a crucial additional signal.

    ## Summary

    ✅ **GCN** generalizes convolution to graphs via normalized neighborhood aggregation
    ✅ GCNs significantly outperform MLPs on node classification when the graph has **homophily**
    ✅ Two GCN layers capture 2-hop neighborhood information
    ✅ PyTorch Geometric makes building GCNs simple with `GCNConv`
    ✅ The graph structure provides a powerful inductive bias for learning

    **Next up:** Graph Attention Networks (GAT) — learning which neighbors matter most!
    """)
    return


@app.cell
def _():
    return


if __name__ == "__main__":
    app.run()
