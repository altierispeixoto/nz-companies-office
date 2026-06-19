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
    from torch_geometric.utils import train_test_split_edges, negative_sampling
    import warnings
    warnings.filterwarnings("ignore")
    return F, GCNConv, mo, negative_sampling, nn, torch, train_test_split_edges


@app.cell
def _(mo):
    mo.md("""
    # GNN Workshop 6: Advanced Topics

    This final workshop covers advanced GNN applications and topics:

    1. **Link Prediction** — Predicting missing edges
    2. **Explainability** — Understanding GNN predictions
    3. **Scalability** — Billion-node graphs
    4. **Real-World Deployment** — Production GNNs
    5. **Research Frontiers** — Where the field is heading
    """)
    return


@app.cell
def _(mo):
    mo.md("""
    # Part 1: Link Prediction

    **Link prediction** asks: "Given two nodes, should there be an edge between them?"

    ## Applications

    - **Social networks**: Friend recommendations ("people you may know")
    - **E-commerce**: Product recommendations
    - **Biology**: Predicting protein-protein interactions
    - **Knowledge graphs**: Completing missing facts

    ## The Approach

    1. Train a GNN to produce node embeddings
    2. For a pair of nodes (u, v), compute a **score** based on their embeddings
    3. Score functions: dot product, cosine similarity, MLP
    """)
    return


@app.cell
def _(mo):
    mo.md("""
    ## Link Prediction with GNNs

    We'll use the Cora dataset: hide some edges, train to predict them.
    """)
    return


@app.cell
def _(F, GCNConv, mo, nn, torch, train_test_split_edges):
    from torch_geometric.datasets import Planetoid

    dataset_lp = Planetoid(root="/tmp/Cora", name="Cora")
    data_full_lp = dataset_lp[0]

    data_lp = train_test_split_edges(data_full_lp, val_ratio=0.05, test_ratio=0.1)

    class LinkPredictor(nn.Module):
        def __init__(self, in_dim, hidden_dim):
            super().__init__()
            self.conv1 = GCNConv(in_dim, hidden_dim)
            self.conv2 = GCNConv(hidden_dim, hidden_dim)

        def forward(self, x, edge_index):
            x = F.relu(self.conv1(x, edge_index))
            x = self.conv2(x, edge_index)
            return x

        def predict(self, z, edge_index):
            return (z[edge_index[0]] * z[edge_index[1]]).sum(dim=1)

    model_lp = LinkPredictor(data_lp.x.shape[1], 64)
    opt_lp = torch.optim.Adam(model_lp.parameters(), lr=0.01)

    mo.md(f"**Link Prediction Model**: {sum(p.numel() for p in model_lp.parameters()):,} parameters")
    return data_lp, model_lp, opt_lp


@app.cell
def _(F, data_lp, mo, model_lp, negative_sampling, opt_lp, torch):
    for _ep_lp in range(100):
        model_lp.train()
        opt_lp.zero_grad()

        z_lp = model_lp(data_lp.x, data_lp.train_pos_edge_index)

        pos_score_lp = model_lp.predict(z_lp, data_lp.train_pos_edge_index)
        pos_loss_lp = -F.logsigmoid(pos_score_lp).mean()

        neg_edge_index_lp = negative_sampling(
            edge_index=data_lp.train_pos_edge_index,
            num_nodes=data_lp.num_nodes,
            num_neg_samples=data_lp.train_pos_edge_index.size(1),
        )
        neg_score_lp = model_lp.predict(z_lp, neg_edge_index_lp)
        neg_loss_lp = -F.logsigmoid(-neg_score_lp).mean()

        loss_lp = pos_loss_lp + neg_loss_lp
        loss_lp.backward()
        opt_lp.step()

        if (_ep_lp + 1) % 50 == 0:
            mo.output.append(mo.md(f"Epoch {_ep_lp + 1:3d}/100 | Loss: {loss_lp.item():.4f}"))

    model_lp.eval()
    with torch.no_grad():
        z_lp = model_lp(data_lp.x, data_lp.train_pos_edge_index)
        pos_score_lp = model_lp.predict(z_lp, data_lp.test_pos_edge_index)
        neg_score_lp = model_lp.predict(z_lp, data_lp.test_neg_edge_index)

        correct_pos_lp = (pos_score_lp > 0).sum().item()
        correct_neg_lp = (neg_score_lp < 0).sum().item()
        total_lp = pos_score_lp.size(0) + neg_score_lp.size(0)
        accuracy_lp = (correct_pos_lp + correct_neg_lp) / total_lp

    mo.md(f"**Link Prediction Test Accuracy**: {accuracy_lp:.2%}")
    return (accuracy_lp,)


@app.cell
def _(accuracy_lp, mo):
    mo.md(f"""
    **Link prediction results:**
    - **Accuracy**: {accuracy_lp:.2%}
    - The model learned to distinguish real edges from non-edges based on node embeddings!

    This is how social networks recommend friends — and how Google Knowledge Graph completes missing facts.
    """)
    return


@app.cell
def _(mo):
    mo.md("""
    # Part 2: GNN Explainability

    Why did my GNN make that prediction? This is critical for:
    - **Trust**: Would you trust a medical diagnosis model you can't understand?
    - **Debugging**: Finding spurious correlations
    - **Science**: Discovering which parts of a molecule determine toxicity

    ## GNNExplainer (Ying et al., 2019)

    GNNExplainer finds the **subgraph** and **feature subset** most responsible for a prediction:

    1. Learn a **mask** over edges (which edges matter?)
    2. Learn a **mask** over features (which features matter?)
    3. Maximize mutual information between the masked graph and the prediction

    > The highlighted subgraph tells us *why* the model made its decision.
    """)
    return


@app.cell
def _(mo):
    mo.md("""
    ## Interpreting GNN Predictions: Attention-Based

    Even without formal explainability tools, GAT's **attention weights** give us interpretability:

    ```python
    # GAT returns attention weights
    x, (edge_index, attn_weights) = gat_conv(x, edge_index, return_attention_weights=True)

    # attn_weights[i] tells us how much node u attends to node v
    ```

    For GCN and GraphSAGE, the GNNExplainer can be used:

    ```python
    from torch_geometric.explain import GNNExplainer

    explainer = GNNExplainer(model, epochs=200)
    node_idx = 10
    node_feat_mask, edge_mask = explainer.explain_node(node_idx, x, edge_index)
    ```

    > **Note**: `torch-geometric>=2.0` includes integrated explainability tools.
    """)
    return


@app.cell
def _(mo):
    mo.md("""
    # Part 3: Scalability

    Real-world graphs are **HUGE**:
    - Facebook: 3 billion users, trillions of edges
    - Web graph: billions of pages
    - Knowledge graphs: billions of facts

    ## Techniques for Scaling GNNs

    | Technique | What It Does |
    |-----------|-------------|
    | **Neighbor Sampling** (GraphSAGE) | Sample fixed-size neighborhoods |
    | **Cluster-GCN** | Cluster nodes, train on subgraphs |
    | **GraphSAINT** | Sample subgraphs as mini-batches |
    | **ShadowGNN** | Decouple sampling from training |
    | **Distributed training** | Split graph across GPUs |

    ### Cluster-GCN

    1. Partition the graph into clusters (METIS algorithm)
    2. Each mini-batch = one cluster (dense connections inside, sparse between)
    3. Train on cluster subgraphs

    This is **much more efficient** than neighbor sampling because it leverages the graph's natural community structure.
    """)
    return


@app.cell
def _(mo):
    mo.md("""
    # Part 4: Real-World Deployment

    ## ML Pipeline for Production GNNs

    ```
    Raw Data → Graph Construction → Feature Engineering → GNN Training → Deployment → Monitoring
    ```

    ### Key Challenges

    1. **Graph Construction**
       - Raw data is rarely in graph format
       - Need to define nodes, edges, features
       - Temporal aspects: graphs change over time

    2. **Feature Engineering**
       - Node features: embeddings, statistics, metadata
       - Edge features: weights, types, timestamps
       - Structural features: degree, PageRank, community

    3. **Inference at Scale**
       - Full-batch inference may be impossible
       - Use mini-batch or approximate methods
       - Consider model quantization

    4. **Serving Infrastructure**

       ```python
       # Simple deployment with ONNX
       import torch.onnx

       dummy_x = torch.randn(1, in_dim)
       dummy_edge_index = torch.tensor([[0], [0]])
       torch.onnx.export(model, (dummy_x, dummy_edge_index), "gnn.onnx")
       ```

    5. **Monitoring**
       - Embedding drift detection
       - Prediction confidence tracking
       - Graph structure changes

    ### Tools for Production
    - **PyTorch Geometric + TorchServe**: Model serving
    - **ONNX Runtime**: Cross-platform inference
    - **DGL + AWS SageMaker**: Cloud deployment
    - **Neo4j + GDS**: Graph database with built-in GNNs
    """)
    return


@app.cell
def _(mo):
    mo.md("""
    # Part 5: Research Frontiers

    ## Where is GNN Research Heading?

    ### 🔮 Graph Foundation Models
    Large pre-trained models that work across diverse graphs and tasks (similar to GPT for text).

    ### ⏰ Temporal Graphs
    Most real graphs change over time:
    - Social network: new friendships form
    - Financial network: transactions happen
    - Transportation: traffic fluctuates

    **TGAT** and **TGN** extend GNNs to handle temporal dynamics.

    ### 🔬 Drug Discovery & Science
    - **AlphaFold**: Protein folding with graph representations
    - **Molecule generation**: GNNs + diffusion models for drug design
    - **Materials discovery**: Predicting crystal properties

    ### 🧠 Graph Transformers
    Adapting the Transformer architecture to graphs:
    - Positional encodings (Laplacian eigenvectors)
    - Full attention over all nodes (for small graphs)
    - Promising results on molecular benchmarks

    ### 🤔 Open Challenges
    1. **Oversmoothing**: After many layers, all node embeddings become identical
    2. **Heterophily**: When connected nodes tend to have *different* labels (GCN fails)
    3. **Distribution shift**: Training and test graphs come from different distributions
    4. **Causality**: Moving beyond correlation to causal reasoning on graphs
    """)
    return


@app.cell
def _(mo):
    mo.md("""
    # Part 6: Your Next Steps

    ## Learning Path

    ```mermaid
    graph TD
        A[Graph Workshop 1-6] --> B[GNN Workshop 1-6]
        B --> C[Paper Implementations]
        B --> D[PyG Documentation]
        B --> E[Personal Projects]
        C --> F[Your Research / Production]
        D --> F
        E --> F
    ```

    ## 💡 Project Ideas

    | Difficulty | Project |
    |-----------|---------|
    | ⭐ | Node classification on your own graph data |
    | ⭐⭐ | Link prediction for friend recommendations |
    | ⭐⭐⭐ | Graph classification of molecules (QM9 dataset) |
    | ⭐⭐⭐⭐ | Temporal GNN for stock/buy prediction |
    | ⭐⭐⭐⭐⭐ | Graph generation for drug discovery |

    ## 📚 Key Papers

    | Paper | Year | What It Introduced |
    |-------|------|-------------------|
    | GCN (Kipf & Welling) | 2017 | Graph convolution |
    | GraphSAGE (Hamilton et al.) | 2017 | Inductive learning + sampling |
    | GAT (Veličković et al.) | 2018 | Graph attention |
    | GIN (Xu et al.) | 2019 | Maximal expressive power |
    | DiffPool (Ying et al.) | 2018 | Hierarchical pooling |
    | GNNExplainer (Ying et al.) | 2019 | Explainability |
    | Cluster-GCN (Chiang et al.) | 2019 | Large-scale training |
    | Graph Transformers | 2021+ | Attention on graphs |

    ## 🛠️ Libraries

    - **PyTorch Geometric (PyG)**: What we used — most popular GNN library
    - **DGL (Deep Graph Library)**: Alternative to PyG, good for large graphs
    - **Jraph** (JAX): For JAX users
    - **TensorFlow GNN**: For TF ecosystem
    - **NetworkX**: For graph analysis (pre-GNN)
    """)
    return


@app.cell
def _(mo):
    mo.md("""
    ## Workshop Summary

    | Notebook | Topic | You Learned |
    |----------|-------|-------------|
    | **1** | GNN Foundations | Message passing paradigm, Data objects |
    | **2** | GCN | Graph convolution, node classification |
    | **3** | GAT | Attention mechanisms, multi-head attention |
    | **4** | GraphSAGE | Inductive learning, neighborhood sampling |
    | **5** | Graph Classification | Pooling, readout, molecular property prediction |
    | **6** | Advanced Topics | Link prediction, explainability, scalability, frontiers |

    ## Congratulations! 🎉

    You've gone from **graph foundations** to **cutting-edge GNN research**. You now have the knowledge to:

    ✅ Choose the right GNN architecture for your problem
    ✅ Implement and train GNNs with PyTorch Geometric
    ✅ Scale GNNs to large graphs
    ✅ Apply GNNs to real-world problems

    **The graph is everywhere — go explore it!** 🚀
    """)
    return


if __name__ == "__main__":
    app.run()
