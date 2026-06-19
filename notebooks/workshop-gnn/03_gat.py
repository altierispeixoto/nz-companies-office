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
    from torch_geometric.nn import GATConv, GCNConv
    from torch_geometric.datasets import Planetoid
    import warnings
    warnings.filterwarnings("ignore")
    return F, GATConv, GCNConv, Planetoid, mo, nn, nx, plt, torch


@app.cell
def _(mo):
    mo.md("""
    # GNN Workshop 3: Graph Attention Networks (GAT)

    The **Graph Attention Network** (Veličković et al., 2018) addresses a key limitation of GCNs:

    > **GCN**: All neighbors contribute equally to the aggregation
    > **GAT**: Each neighbor contributes a *learned weight* (attention)

    ## Why Attention?

    Not all neighbors are equally important. In a citation network:
    - A paper citing your work is important
    - A paper citing completely unrelated work is less important

    GAT learns to **pay more attention** to relevant neighbors and **ignore** irrelevant ones.
    """)
    return


@app.cell
def _(mo):
    mo.md(r"""
    ## The Attention Mechanism

    For each edge \((i, j)\), GAT computes an **attention coefficient**:

    $$e_{ij} = 	ext{LeakyReLU}\left(a^T [W h_i \, \Vert \, W h_j]
    ight)$$

    Then normalizes across neighbors with **softmax**:

    $$\alpha_{ij} =
    rac{\exp(e_{ij})}{\sum_{k \in N(i)} \exp(e_{ik})}$$

    Finally, **aggregates** using attention weights:

    $$h_i' = \sigma\left(\sum_{j \in N(i)} \alpha_{ij} W h_j
    ight)$$

    ### Multi-Head Attention

    GAT uses **K independent attention heads** and concatenates (or averages) their outputs:

    $$h_i' = \Big\Vert_{k=1}^{K} \sigma\left(\sum_{j \in N(i)} \alpha_{ij}^{(k)} W^{(k)} h_j
    ight)$$

    This stabilizes learning and captures different types of relationships.
    """)
    return


@app.cell
def _(mo):
    mo.md("""
    ## GCN vs GAT: Visual Comparison

    | Aspect | GCN | GAT |
    |--------|-----|-----|
    | **Neighbor weighting** | Equal (normalized degree) | Learned (attention) |
    | **Expressiveness** | Fixed weights | Dynamic, per-node-pair weights |
    | **Interpretability** | Harder | Attention weights can be visualized |
    | **Inductive** | Works | Works (attention is per-node-pair) |
    | **Parameters** | Fewer | More (due to attention mechanism) |
    """)
    return


@app.cell
def _(Planetoid):
    dataset = Planetoid(root="/tmp/Cora", name="Cora")
    data_cora = dataset[0]
    in_dim = data_cora.x.shape[1]
    out_dim = dataset.num_classes
    return data_cora, in_dim, out_dim


@app.cell
def _(F, GATConv, in_dim, nn, out_dim, torch):
    class GAT(nn.Module):
        def __init__(self, in_dim, hidden_dim, out_dim, heads=8, dropout=0.6):
            super().__init__()
            self.conv1 = GATConv(in_dim, hidden_dim, heads=heads, dropout=dropout)
            self.conv2 = GATConv(hidden_dim * heads, out_dim, heads=1, concat=False, dropout=dropout)
            self.dropout = dropout

        def forward(self, x, edge_index):
            x = F.dropout(x, p=self.dropout, training=self.training)
            x = self.conv1(x, edge_index)
            x = F.elu(x)
            x = F.dropout(x, p=self.dropout, training=self.training)
            x = self.conv2(x, edge_index)
            return F.log_softmax(x, dim=1)

    model_gat = GAT(in_dim, 8, out_dim, heads=8)
    optimizer_gat = torch.optim.Adam(model_gat.parameters(), lr=0.005, weight_decay=5e-4)
    return model_gat, optimizer_gat


@app.cell
def _(F, data_cora, mo, model_gat, optimizer_gat, torch):
    gat_loss_hist = []
    gat_acc_hist = []

    for _ep in range(200):
        model_gat.train()
        optimizer_gat.zero_grad()
        out_gat = model_gat(data_cora.x, data_cora.edge_index)
        l_gat = F.nll_loss(out_gat[data_cora.train_mask], data_cora.y[data_cora.train_mask])
        l_gat.backward()
        optimizer_gat.step()

        model_gat.eval()
        pred_gat = out_gat.argmax(dim=1)
        train_acc_gat = (pred_gat[data_cora.train_mask] == data_cora.y[data_cora.train_mask]).float().mean()
        val_acc_gat = (pred_gat[data_cora.val_mask] == data_cora.y[data_cora.val_mask]).float().mean()

        gat_loss_hist.append(l_gat.item())
        gat_acc_hist.append(train_acc_gat.item())

        if (_ep + 1) % 50 == 0:
            mo.output.append(mo.md(f"Epoch {_ep + 1:3d}/200 | Loss: {l_gat.item():.4f} | Train Acc: {train_acc_gat:.3f} | Val Acc: {val_acc_gat:.3f}"))

    model_gat.eval()
    with torch.no_grad():
        out_gat_final = model_gat(data_cora.x, data_cora.edge_index)
        test_acc_gat = (out_gat_final.argmax(dim=1)[data_cora.test_mask] == data_cora.y[data_cora.test_mask]).float().mean()
    return gat_acc_hist, test_acc_gat


@app.cell
def _(mo):
    mo.md("""
    ## Visualizing Attention Weights

    One of GAT's superpowers: we can visualize **which neighbors each node pays attention to**.
    """)
    return


@app.cell
def _(F, data_cora, mo, model_gat, nx, plt, torch):
    model_gat.eval()
    with torch.no_grad():
        x_attn = F.dropout(data_cora.x, p=0.6, training=False)
        x_attn_out, attn_weights = model_gat.conv1(x_attn, data_cora.edge_index, return_attention_weights=True)

    attn_edge_index = attn_weights[0]
    attn_scores = attn_weights[1].mean(dim=1).numpy()

    edge_attn = {}
    for _ei in range(attn_edge_index.shape[1]):
        u, v = attn_edge_index[0, _ei].item(), attn_edge_index[1, _ei].item()
        edge_attn[(u, v)] = attn_scores[_ei]

    G_plot = nx.Graph()
    G_plot.add_edges_from([(u, v) for u, v in data_cora.edge_index.t().tolist()])

    fig_attn, ax_attn = plt.subplots(figsize=(14, 10))
    pos_attn = nx.spring_layout(G_plot, seed=42, iterations=30)

    node_color = plt.cm.tab10(data_cora.y.numpy() / 7)
    nx.draw_networkx_nodes(G_plot, pos_attn, node_color=node_color, node_size=30, alpha=0.8, ax=ax_attn)

    edges_subset = list(edge_attn.items())[:500]
    if edges_subset:
        e_list, e_weights = zip(*edges_subset)
        edge_colors = list(e_weights)
        nx.draw_networkx_edges(
            G_plot, pos_attn, edgelist=e_list,
            width=[w * 10 for w in e_weights],
            edge_color=edge_colors, edge_cmap=plt.cm.YlOrRd,
            alpha=0.6, ax=ax_attn,
        )

    ax_attn.set_title("GAT Attention Weights (thicker = more attention)", fontsize=14)
    ax_attn.axis("off")
    plt.tight_layout()
    mo.mpl.interactive(plt.gcf())
    return attn_edge_index, attn_scores


@app.cell
def _(mo):
    mo.md(r"""
    ## GCN vs GAT: Results

    GAT often outperforms GCN because:
    1. **Adaptive weighting**: GAT learns which neighbors matter, rather than assuming all are equally important
    2. **Multi-head attention**: Multiple attention heads capture different types of relationships
    3. **Robustness**: Attention weights can ignore noisy or irrelevant neighbors

    However, GAT has more parameters and may need more data to train effectively.

    ## Summary

    ✅ **GAT** introduces **learned attention weights** for neighbor aggregation
    ✅ **Multi-head attention** stabilizes training and captures diverse relationships
    ✅ Attention weights are **interpretable** — we can see which neighbors matter
    ✅ GAT often outperforms GCN, especially on graphs with varying neighbor importance
    ✅ Built with `GATConv` in PyTorch Geometric

    **Next up:** GraphSAGE — scaling GNNs to large graphs with inductive learning!
    """)
    return


@app.cell
def _(data_cora, mo):
    target_plot = mo.ui.slider(0, data_cora.x.shape[0] - 1, step=1, value=0, label="Show attention for node:")
    return (target_plot,)


@app.cell
def _(attn_edge_index, attn_scores, data_cora, mo, plt, target_plot):
    node_idx = target_plot.value

    neighbor_attentions = []
    for _ei in range(attn_edge_index.shape[1]):
        if attn_edge_index[1, _ei].item() == node_idx:
            neighbor = attn_edge_index[0, _ei].item()
            score = attn_scores[_ei]
            neighbor_attentions.append((neighbor, score))

    neighbor_attentions.sort(key=lambda x: x[1], reverse=True)

    fig_target, ax_target = plt.subplots(figsize=(8, max(4, len(neighbor_attentions) * 0.3)))
    if neighbor_attentions:
        neighbors = [f"Node {n}" for n, _ in neighbor_attentions]
        scores = [s for _, s in neighbor_attentions]
        colors_nei = [plt.cm.YlOrRd(s / max(scores)) for s in scores]
        ax_target.barh(neighbors, scores, color=colors_nei)
        ax_target.set_xlabel("Attention Weight")
        ax_target.set_title(f"Attention weights for Node {node_idx} (class: {data_cora.y[node_idx].item()})")
        ax_target.invert_yaxis()

    plt.tight_layout()
    mo.mpl.interactive(plt.gcf())
    return


@app.cell
def _(F, GCNConv, data_cora, gat_acc_hist, mo, nn, plt, test_acc_gat, torch):
    class GCN_for_comp(nn.Module):
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

    gcn_comp_model = GCN_for_comp(data_cora.x.shape[1], 16, 7)
    gcn_comp_opt = torch.optim.Adam(gcn_comp_model.parameters(), lr=0.01, weight_decay=5e-4)

    gcn_acc_hist = []
    for _ep in range(200):
        gcn_comp_model.train()
        gcn_comp_opt.zero_grad()
        out_gcn_c = gcn_comp_model(data_cora.x, data_cora.edge_index)
        loss_gcn_c = F.nll_loss(out_gcn_c[data_cora.train_mask], data_cora.y[data_cora.train_mask])
        loss_gcn_c.backward()
        gcn_comp_opt.step()
        gcn_comp_model.eval()
        pred_gcn_c = out_gcn_c.argmax(dim=1)
        gcn_acc_hist.append((pred_gcn_c[data_cora.val_mask] == data_cora.y[data_cora.val_mask]).float().mean().item())

    gcn_comp_model.eval()
    with torch.no_grad():
        gcn_test = (gcn_comp_model(data_cora.x, data_cora.edge_index).argmax(dim=1)[data_cora.test_mask] == data_cora.y[data_cora.test_mask]).float().mean()

    fig_comp, ax_comp = plt.subplots(figsize=(10, 6))
    ax_comp.plot(gcn_acc_hist, label=f"GCN (test: {gcn_test:.2%})", color="#339af0", linewidth=2)
    ax_comp.plot(gat_acc_hist, label=f"GAT (test: {test_acc_gat:.2%})", color="#e03131", linewidth=2)
    ax_comp.set_xlabel("Epoch")
    ax_comp.set_ylabel("Validation Accuracy")
    ax_comp.set_title("GCN vs GAT on Cora")
    ax_comp.legend()
    ax_comp.grid(alpha=0.3)
    plt.tight_layout()
    mo.mpl.interactive(plt.gcf())
    return


if __name__ == "__main__":
    app.run()
