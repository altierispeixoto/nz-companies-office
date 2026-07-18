# ---
# marimo-version: 0.23.9
# license: Apache-2.0
# ---

import marimo

__generated_with = "0.23.9"
app = marimo.App(width="full")


@app.cell
def _():
    import marimo as mo
    import matplotlib.pyplot as plt
    import networkx as nx
    import numpy as np
    import torch
    from torch import nn
    from torch.nn import functional as F
    from torch_geometric.data import Data
    from torch_geometric.utils import to_networkx

    return Data, F, mo, nn, np, nx, plt, to_networkx, torch


@app.cell
def _(mo):
    mo.md(r"""
    # GNN Workshop 1: Foundations & Message Passing

    Welcome to the first notebook in the Graph Neural Networks workshop! This series assumes you understand basic graph concepts (nodes, edges, adjacency). If not, check the **Graph Workshop** (notebooks/workshop/) first.

    ## Why GNNs?

    Traditional deep learning (CNNs, RNNs, Transformers) assumes **grid-like data**:
    - Images: regular 2D grid of pixels
    - Text: sequential 1D tokens
    - Tabular: fixed set of features

    **Graphs are different**: each node has a variable number of neighbors, and there's no fixed ordering. We need architectures that can handle this **irregular structure**.

    ## The Core Idea: Message Passing

    GNNs are built on a simple yet powerful idea:

    > Each node **aggregates information** from its neighbors and **updates** its own representation.

    After enough rounds of message passing, every node knows about its local neighborhood structure.

    $$h_v^{(k+1)} = \text{UPDATE}^{(k)}\left(h_v^{(k)}, \text{AGGREGATE}^{(k)}\left(\{h_u^{(k)} : u \in N(v)\}
    \right)
    \right)$$
    """)
    return


@app.cell
def _(mo):
    mo.md("""
    ## Visualizing Message Passing

    Let's create a small graph and see how information flows from node to node:
    """)
    return


@app.cell
def _(Data, mo, np, nx, plt, to_networkx, torch):
    edge_index = torch.tensor(
        [
            [0, 0, 1, 2, 3, 3, 4],
            [1, 3, 2, 3, 4, 5, 5],
        ],
        dtype=torch.long,
    )

    x = torch.tensor(
        [
            [1.0, 0.0],
            [0.0, 1.0],
            [0.5, 0.5],
            [0.8, 0.2],
            [0.1, 0.9],
            [0.3, 0.7],
        ]
    )

    data = Data(x=x, edge_index=edge_index)
    G_mp = to_networkx(data)

    fig_mp, (ax_before, ax_after) = plt.subplots(1, 2, figsize=(16, 6))
    pos_mp = nx.spring_layout(G_mp, seed=42)

    colors_mp = [plt.cm.RdYlBu(val[0]) for val in x.numpy()]

    nx.draw_networkx_nodes(G_mp, pos_mp, node_color=colors_mp, node_size=600, ax=ax_before, edgecolors="black")
    nx.draw_networkx_edges(G_mp, pos_mp, width=2, alpha=0.5, ax=ax_before)
    nx.draw_networkx_labels(G_mp, pos_mp, font_size=10, ax=ax_before)
    ax_before.set_title("Node Features Before Message Passing", fontsize=13)
    ax_before.axis("off")

    edge_index_np = edge_index.numpy()
    for u, v in zip(edge_index_np[0], edge_index_np[1]):
        mid = ((pos_mp[u][0] + pos_mp[v][0]) / 2, (pos_mp[u][1] + pos_mp[v][1]) / 2)
        ax_before.annotate(
            "",
            xy=pos_mp[v],
            xytext=pos_mp[u],
            fontsize=8,
            ha="center",
            arrowprops=dict(color="gray", lw=1.5, connectionstyle="arc3,rad=0.2", arrowstyle="->"),
        )

    nx.draw_networkx_nodes(G_mp, pos_mp, node_color=colors_mp, node_size=600, ax=ax_after, edgecolors="black")
    nx.draw_networkx_edges(G_mp, pos_mp, width=2, alpha=0.5, ax=ax_after)
    nx.draw_networkx_labels(G_mp, pos_mp, font_size=10, ax=ax_after)

    for u, v in zip(edge_index_np[0], edge_index_np[1]):
        mid = ((pos_mp[u][0] + pos_mp[v][0]) / 2, (pos_mp[u][1] + pos_mp[v][1]) / 2)
        angle = np.arctan2(pos_mp[v][1] - pos_mp[u][1], pos_mp[v][0] - pos_mp[u][0])
        offset = 0.06
        mid2 = (mid[0] + offset * np.sin(angle), mid[1] - offset * np.cos(angle))
        ax_after.annotate(
            f"msg: {u}→{v}",
            xy=mid2,
            fontsize=7,
            ha="center",
            bbox=dict(boxstyle="round,pad=0.2", facecolor="lightyellow", edgecolor="none", alpha=0.8),
        )
        ax_after.annotate(
            "",
            xy=pos_mp[v],
            xytext=pos_mp[u],
            fontsize=8,
            ha="center",
            arrowprops=dict(arrowstyle="->", color="orange", lw=2, connectionstyle="arc3,rad=0.2"),
        )

    ax_after.set_title("Messages Flowing Along Edges", fontsize=13)
    ax_after.axis("off")

    plt.tight_layout()
    mo.mpl.interactive(plt.gcf())
    return edge_index, x


@app.cell
def _(mo):
    mo.md(r"""
    ## Building a Message Passing Layer from Scratch

    Let's implement the simplest GNN layer — **Graph Convolution (GCN)** — from scratch. The GCN layer does three things:

    1. **Message**: Each neighbor sends its features to the center node
    2. **Aggregate**: The center node sums up all neighbor messages
    3. **Update**: The center node transforms the aggregated message + its own features

    $$h_v' = W \cdot \left(
    \frac{1}{|N(v)|} \sum_{u \in N(v)} h_u
    \right)$$

    where \(W\) is a learnable weight matrix.
    """)
    return


@app.cell
def _(F, edge_index, nn, torch, x):
    class SimpleMessagePassing(nn.Module):
        def __init__(self, in_dim, out_dim):
            super().__init__()
            self.W = nn.Linear(in_dim, out_dim)

        def forward(self, x, edge_index):
            src, dst = edge_index
            neighbor_features = x[src]
            aggregated = torch.zeros_like(x)
            aggregated.index_add_(0, dst, neighbor_features)
            deg = torch.bincount(dst, minlength=x.size(0)).float().clamp(min=1)
            aggregated = aggregated / deg.unsqueeze(1)
            return F.relu(self.W(aggregated))

    mp_layer = SimpleMessagePassing(2, 4)
    mp_out = mp_layer(x, edge_index)
    return (mp_out,)


@app.cell
def _(mo, mp_out, x):
    mo.md(f"""
    **Input shape**: {tuple(x.shape)} (6 nodes, 2 features each)
    **Output shape**: {tuple(mp_out.shape)} (6 nodes, 4 features each)

    Each node now has a 4-dimensional feature vector that incorporates information from its neighbors!
    """)
    return


@app.cell
def _(mo):
    mo.md(r"""
    ## PyTorch Geometric's Data Object

    PyTorch Geometric uses a `Data` object to represent graphs. Key attributes:

    | Attribute | Shape | Description |
    |-----------|-------|-------------|
    | `x` | `[N, F]` | Node features (N nodes, F features) |
    | `edge_index` | `[2, E]` | Graph connectivity (edge list) |
    | `y` | `[N]` or `[1]` | Labels (per-node or per-graph) |
    | `edge_attr` | `[E, D]` | Edge features (optional) |
    | `train_mask` | `[N]` | Boolean mask for training nodes |
    | `val_mask` / `test_mask` | `[N]` | Validation/test masks |
    """)
    return


@app.cell
def _(Data, torch):
    demo_data = Data(
        x=torch.randn(4, 3),
        edge_index=torch.tensor([[0, 1, 2, 0], [1, 2, 3, 3]]),
        y=torch.tensor([0, 0, 1, 1]),
    )
    return


@app.cell
def _(mo):
    mo.md(r"""
    ## Interactive: Watch Message Passing in Action

    Let's trace how information flows from a source node through the graph with multiple layers:
    """)
    return


@app.cell
def _(mo):
    hops = mo.ui.slider(1, 5, step=1, value=2, label="Number of message passing steps (layers)")
    target_node = mo.ui.slider(0, 5, step=1, value=0, label="Target node to track")
    return hops, target_node


@app.cell
def _(Data, edge_index, hops, nx, plt, target_node, to_networkx, torch):
    x_track = torch.randn(6, 1)
    edge_index_track = edge_index.clone()
    data_track = Data(x=x_track, edge_index=edge_index_track)
    G_track = to_networkx(data_track)

    fig_track, axes_track = plt.subplots(2, 3, figsize=(18, 12))
    pos_track = nx.spring_layout(G_track, seed=42)

    for step in range(min(hops.value, 6)):
        ax = axes_track[step // 3, step % 3]

        reached = {target_node.value}
        frontier = {target_node.value}
        src, dst = edge_index_track.numpy()
        for _ in range(step + 1):
            new_frontier = set()
            for _fn in frontier:
                mask = dst == _fn
                new_frontier.update(src[mask].tolist())
                mask2 = src == _fn
                new_frontier.update(dst[mask2].tolist())
            reached.update(new_frontier)
            frontier = new_frontier

        colors_track = []
        for _n in G_track.nodes():
            if _n == target_node.value:
                colors_track.append("#ff6b6b")
            elif _n in reached:
                colors_track.append("#ffd43b")
            else:
                colors_track.append("lightblue")

        nx.draw_networkx_nodes(G_track, pos_track, node_color=colors_track, node_size=500, ax=ax)
        nx.draw_networkx_edges(G_track, pos_track, width=1.5, alpha=0.4, ax=ax)
        nx.draw_networkx_labels(G_track, pos_track, ax=ax)
        ax.set_title(f"After {step + 1} Message Passing Step(s)", fontsize=12)
        ax.axis("off")

    for _i in range(hops.value, 6):
        ax = axes_track[_i // 3, _i % 3]
        ax.axis("off")

    plt.tight_layout()
    return


@app.cell
def _(mo):
    mo.md(r"""
    ## The Receptive Field of a GNN

    A key property: after \(k\) layers of message passing, a node's representation contains information from its \(k\)-hop neighborhood.

    > 🧠 **Analogy**: If the graph is a social network and you're the target node:
    > - 1 layer = you know your direct friends
    > - 2 layers = you know friends-of-friends
    > - 3 layers = you know friends-of-friends-of-friends
    > - ... and so on

    This is the GNN's **receptive field** — analogous to the field of view in a CNN.

    ### Three Key Design Decisions

    When building a GNN layer, we must choose:

    1. **AGGREGATE**: How do we combine neighbor messages? (sum, mean, max, attention)
    2. **UPDATE**: How do we combine the node's own features with the aggregated message? (concat, add, gate)
    3. **Number of layers**: How many hops of neighborhood do we need?
    """)
    return


@app.cell
def _(F, edge_index, nn, torch, x):
    class CompareAggregators(nn.Module):
        def __init__(self, in_dim, out_dim, agg="mean"):
            super().__init__()
            self.W = nn.Linear(in_dim, out_dim)
            self.agg = agg

        def forward(self, x, edge_index):
            src, dst = edge_index
            msgs = x[src]
            agg_out = torch.zeros_like(x)
            if self.agg == "sum":
                agg_out.index_add_(0, dst, msgs)
            elif self.agg == "mean":
                agg_out.index_add_(0, dst, msgs)
                deg = torch.bincount(dst, minlength=x.size(0)).float().clamp(min=1)
                agg_out = agg_out / deg.unsqueeze(1)
            elif self.agg == "max":
                agg_out.scatter_reduce_(0, dst.unsqueeze(1).expand(-1, x.size(1)), msgs, reduce="amax")
            return F.relu(self.W(agg_out))

    sum_layer = CompareAggregators(2, 4, "sum")
    mean_layer = CompareAggregators(2, 4, "mean")
    max_layer = CompareAggregators(2, 4, "max")

    out_sum = sum_layer(x, edge_index)
    out_mean = mean_layer(x, edge_index)
    out_max = max_layer(x, edge_index)
    return


@app.cell
def _(F, nn, torch):
    class CompareUpdate(nn.Module):
        def __init__(self, in_dim, out_dim, mode="concat"):
            super().__init__()
            self.mode = mode
            if mode == "concat":
                self.W = nn.Linear(in_dim * 2, out_dim)
            else:
                self.W = nn.Linear(in_dim, out_dim)
            self.W_self = nn.Linear(in_dim, out_dim) if mode == "add" else None

        def forward(self, x, edge_index):
            src, dst = edge_index
            msgs = x[src]
            agg = torch.zeros_like(x)
            agg.index_add_(0, dst, msgs)
            deg = torch.bincount(dst, minlength=x.size(0)).float().clamp(min=1)
            agg = agg / deg.unsqueeze(1)

            if self.mode == "concat":
                return F.relu(self.W(torch.cat([x, agg], dim=1)))
            elif self.mode == "add":
                return F.relu(self.W(agg) + self.W_self(x))
            else:
                return F.relu(self.W(agg))

    concat_layer = CompareUpdate(2, 4, "concat")
    return


@app.cell
def _(mo):
    mo.md(r"""
    ## Summary

    ✅ GNNs use **message passing** to learn from graph-structured data
    ✅ Each layer aggregates neighbor information and updates node representations
    ✅ The **Data** object in PyTorch Geometric is the fundamental data structure
    ✅ After \(k\) layers, each node knows about its \(k\)-hop neighborhood
    ✅ Key design choices: **AGGREGATE** (sum/mean/max) and **UPDATE** (concat/add)
    ✅ We built a GNN layer from scratch in just a few lines of code!

    **Next up:** Graph Convolutional Networks (GCN) — the most popular GNN architecture.
    """)
    return


@app.cell
def _():
    return


if __name__ == "__main__":
    app.run()
