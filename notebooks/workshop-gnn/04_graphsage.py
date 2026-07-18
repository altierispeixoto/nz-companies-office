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
    import torch
    import torch.nn as nn
    import torch.nn.functional as F
    from torch_geometric.datasets import Planetoid
    from torch_geometric.nn import SAGEConv

    warnings.filterwarnings("ignore")
    return F, Planetoid, SAGEConv, mo, nn, torch


@app.cell
def _(mo):
    mo.md("""
    # GNN Workshop 4: GraphSAGE & Inductive Learning

    ## The Problem with GCN and GAT

    GCN and GAT are **transductive** — they need the **entire graph** during training. If a new node appears after training, you'd need to retrain the model.

    **GraphSAGE** (Hamilton, Ying, Leskovec, 2017) solves this by learning an **aggregator function** that can generalize to unseen nodes.

    | Property | GCN / GAT | GraphSAGE |
    |----------|-----------|-----------|
    | **Learning** | Transductive | Inductive |
    | **New nodes** | Needs retraining | Zero-shot generalization |
    | **Scalability** | Full graph needed | Mini-batch training |
    | **Sampling** | No | Yes (neighborhood sampling) |
    """)
    return


@app.cell
def _(Planetoid):
    dataset = Planetoid(root="/tmp/Cora", name="Cora")
    data = dataset[0]

    in_dim = data.x.shape[1]
    out_dim = dataset.num_classes
    return data, in_dim, out_dim


@app.cell
def _(F, SAGEConv, in_dim, nn, out_dim, torch):
    class GraphSAGE(nn.Module):
        def __init__(self, in_dim, hidden_dim, out_dim, dropout=0.5):
            super().__init__()
            self.conv1 = SAGEConv(in_dim, hidden_dim)
            self.conv2 = SAGEConv(hidden_dim, out_dim)
            self.dropout = dropout

        def forward(self, x, edge_index):
            x = self.conv1(x, edge_index)
            x = F.relu(x)
            x = F.dropout(x, p=self.dropout, training=self.training)
            x = self.conv2(x, edge_index)
            return F.log_softmax(x, dim=1)

    model_sage = GraphSAGE(in_dim, 64, out_dim)
    opt_sage = torch.optim.Adam(model_sage.parameters(), lr=0.01, weight_decay=5e-4)
    return model_sage, opt_sage


@app.cell
def _(F, data, mo, model_sage, opt_sage, torch):
    sage_loss_hist = []
    sage_acc_hist = []

    for _ep_sage in range(200):
        model_sage.train()
        opt_sage.zero_grad()
        out_sage = model_sage(data.x, data.edge_index)
        loss_sage = F.nll_loss(out_sage[data.train_mask], data.y[data.train_mask])
        loss_sage.backward()
        opt_sage.step()

        model_sage.eval()
        pred_sage = out_sage.argmax(dim=1)
        train_acc_sage = (pred_sage[data.train_mask] == data.y[data.train_mask]).float().mean()
        val_acc_sage = (pred_sage[data.val_mask] == data.y[data.val_mask]).float().mean()

        sage_loss_hist.append(loss_sage.item())
        sage_acc_hist.append(train_acc_sage.item())

        if (_ep_sage + 1) % 50 == 0:
            mo.output.append(
                mo.md(
                    f"Epoch {_ep_sage + 1:3d}/200 | Loss: {loss_sage.item():.4f} | Train Acc: {train_acc_sage:.3f} | Val Acc: {val_acc_sage:.3f}"
                )
            )

    model_sage.eval()
    with torch.no_grad():
        out_sage_final = model_sage(data.x, data.edge_index)
        test_acc_sage = (out_sage_final.argmax(dim=1)[data.test_mask] == data.y[data.test_mask]).float().mean()
    return


@app.cell
def _(mo):
    mo.md(r"""
    ## How GraphSAGE Works

    GraphSAGE learns a function that **aggregates features from a sampled neighborhood**:

    $$h_v^{(k+1)} = \sigma\left(W^{(k)} \cdot \left[h_v^{(k)} \Big\Vert \text{AGG}\left(\{h_u^{(k)},
    \forall u \in N_{\text{sampled}}(v)\}
    \right)
    \right]
    \right)$$

    ### Three Aggregator Options:

    1. **Mean aggregator**: Average of neighbor features (like GCN)
    2. **Pooling aggregator**: Element-wise max/mean after an MLP
    3. **LSTM aggregator**: Apply LSTM to a random permutation of neighbors

    ### Neighborhood Sampling

    Instead of using all neighbors (which could be millions), GraphSAGE **samples a fixed number** (e.g., 10, 25) of neighbors at each layer. This makes it **scalable to billion-node graphs**.
    """)
    return


@app.cell
def _(mo):
    mo.md("""
    ## Inductive vs Transductive: A Visual Analogy

    **Transductive (GCN)**: You see the entire puzzle and learn to label each piece. If new pieces are added, you start over.

    **Inductive (GraphSAGE)**: You learn what makes a piece a "corner", "edge", or "center" based on its local pattern. When new pieces appear, you can classify them immediately.

    GraphSAGE learns **structural patterns** that generalize across the graph, not just specific node IDs.
    """)
    return


@app.cell
def _(mo):
    mo.md("""
    ## The Magic of Inductive Learning

    Let's demonstrate inductive capability: we'll train GraphSAGE on a **subset of nodes** and evaluate on **completely held-out nodes**.
    """)
    return


@app.cell
def _(F, SAGEConv, data, mo, nn, torch):
    class InductiveSAGE(nn.Module):
        def __init__(self, in_dim, hidden_dim, out_dim):
            super().__init__()
            self.conv1 = SAGEConv(in_dim, hidden_dim)
            self.conv2 = SAGEConv(hidden_dim, out_dim)

        def forward(self, x, edge_index):
            x = F.relu(self.conv1(x, edge_index))
            return F.log_softmax(self.conv2(x, edge_index), dim=1)

    n_nodes_ind = data.x.shape[0]
    n_train_ind = n_nodes_ind // 2
    n_val_ind = n_nodes_ind // 4
    n_test_ind = n_nodes_ind - n_train_ind - n_val_ind

    indices_ind = torch.randperm(n_nodes_ind)
    train_idx_ind = indices_ind[:n_train_ind]
    val_idx_ind = indices_ind[n_train_ind : n_train_ind + n_val_ind]
    test_idx_ind = indices_ind[n_train_ind + n_val_ind :]

    inductive_mask = torch.zeros(n_nodes_ind, dtype=torch.bool)
    inductive_mask[train_idx_ind] = True
    val_mask_ind = torch.zeros(n_nodes_ind, dtype=torch.bool)
    val_mask_ind[val_idx_ind] = True
    test_mask_ind = torch.zeros(n_nodes_ind, dtype=torch.bool)
    test_mask_ind[test_idx_ind] = True

    model_ind = InductiveSAGE(data.x.shape[1], 64, 7)
    opt_ind = torch.optim.Adam(model_ind.parameters(), lr=0.01, weight_decay=5e-4)

    for _ep_ind in range(200):
        model_ind.train()
        opt_ind.zero_grad()
        out_ind_tr = model_ind(data.x, data.edge_index)
        loss_ind = F.nll_loss(out_ind_tr[inductive_mask], data.y[inductive_mask])
        loss_ind.backward()
        opt_ind.step()

    model_ind.eval()
    with torch.no_grad():
        out_ind_ev = model_ind(data.x, data.edge_index)
        train_acc_ind = (out_ind_ev.argmax(dim=1)[inductive_mask] == data.y[inductive_mask]).float().mean()
        val_acc_ind = (out_ind_ev.argmax(dim=1)[val_mask_ind] == data.y[val_mask_ind]).float().mean()
        test_acc_ind = (out_ind_ev.argmax(dim=1)[test_mask_ind] == data.y[test_mask_ind]).float().mean()

    mo.md(
        f"""
        **Inductive Learning Results:**
        - **Train accuracy** (seen nodes): {train_acc_ind:.2%}
        - **Validation accuracy** (unseen during training): {val_acc_ind:.2%}
        - **Test accuracy** (completely held-out): {test_acc_ind:.2%}

        GraphSAGE can classify **unseen nodes** without retraining! It learned **structural patterns** (how nodes connect) rather than memorizing node identities.
        """
    )
    return


@app.cell
def _(mo):
    mo.md("""
    ## Scaling to Large Graphs: Mini-Batch Training

    For graphs with millions of nodes, we can't fit the full graph in memory. GraphSAGE supports **mini-batch training** with neighborhood sampling.

    ```
    For each mini-batch of target nodes:
        1. Sample K1 neighbors for each target node
        2. Sample K2 neighbors for each of those neighbors
        3. Build a computational graph of the sampled neighborhood
        4. Forward/backward pass on this subgraph
    ```

    This is handled by PyTorch Geometric's `NeighborLoader`:

    ```python
    from torch_geometric.loader import NeighborLoader

    train_loader = NeighborLoader(
        data,
        num_neighbors=[25, 10],  # Sample 25 neighbors at layer 1, 10 at layer 2
        batch_size=256,
        input_nodes=data.train_mask,
    )
    ```
    """)
    return


@app.cell
def _(mo):
    mo.md("""
    ## Comparing All Three Architectures

    | Aspect | GCN | GAT | GraphSAGE |
    |--------|-----|-----|-----------|
    | **Neighbor weighting** | Equal (degree norm) | Learned (attention) | Equal or learned |
    | **Inductive** | ❌ Transductive | ✅ Inductive | ✅ Inductive |
    | **Scalability** | Full graph | Full graph | Mini-batch + sampling |
    | **Key advantage** | Simple, effective | Interpretable, adaptive | Scales to billion nodes |
    | **Year** | 2017 | 2018 | 2017 |

    ### When to Use What?
    - **Small graphs (<10K nodes)**: GCN or GAT
    - **Need interpretability**: GAT (attention weights)
    - **Large graphs (>100K nodes)**: GraphSAGE with sampling
    - **New nodes appear over time**: GraphSAGE (inductive)

    ## Summary

    ✅ **GraphSAGE** enables **inductive learning** — it generalizes to unseen nodes
    ✅ **Neighborhood sampling** makes GNNs scalable to billion-node graphs
    ✅ GraphSAGE learns **aggregator functions**, not node-specific embeddings
    ✅ Multiple aggregation options: mean, pooling, LSTM
    ✅ Built with `SAGEConv` in PyTorch Geometric

    **Next up:** Graph Classification & Pooling — tasks at the graph level!
    """)
    return


if __name__ == "__main__":
    app.run()
