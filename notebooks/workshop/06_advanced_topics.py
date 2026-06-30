# ---
# marimo-version: 0.23.9
# license: Apache-2.0
# ---

import marimo

__generated_with = "0.23.10"
app = marimo.App(width="full")


@app.cell
def _():
    import warnings

    import altair as alt
    import marimo as mo
    import matplotlib.pyplot as plt
    import networkx as nx
    import numpy as np
    import pandas as pd
    from node2vec import Node2Vec
    from sklearn.decomposition import PCA

    warnings.filterwarnings("ignore")
    return Node2Vec, PCA, alt, mo, np, nx, pd, plt


@app.cell
def _(mo):
    mo.md("""
    # 06 — Advanced Topics: Graph Embeddings, Spectral Methods & GNNs

    We've covered foundations, traversal, centrality, and communities. Now let's explore modern graph techniques.

    | # | Topic | What You'll Learn |
    |---|-------|-------------------|
    | 1 | **Graph Embeddings (Node2Vec)** | Turning nodes into vectors for ML |
    | 2 | **Spectral Graph Theory** | What eigenvalues tell us about graphs |
    | 3 | **Graph Neural Networks** | Deep learning on graph-structured data |
    | 4 | **Knowledge Graphs** | Typed, property-rich graphs |
    | 5 | **Where to Go Next** | Books, libraries, and research directions |

    ---

    > **Analogy**: We've learned to read maps, measure cities, find routes, and identify neighborhoods. Now we learn to encode maps into numbers (embeddings), hear the music of graphs (spectral), build AI that reads maps (GNNs), and add rich labels (knowledge graphs).
    """)
    return


@app.cell
def _(mo):
    mo.md("""
    # Part 1: Graph Embeddings

    ## Why Embeddings?

    Most ML algorithms work on **vectors** (tables of numbers), not graphs directly. **Graph embeddings** convert nodes, edges, or entire graphs into dense vector representations while preserving structural properties.

    > A good embedding puts similar nodes close together in vector space.

    **Applications**: Node classification, link prediction, graph visualization, graph generation.
    """)
    return


@app.cell
def _(mo):
    mo.md("""
    ## Node2Vec: Biased Random Walks

    **How it works**: Node2Vec learns embeddings by simulating random walks on the graph and treating them as sentences in a Word2Vec model.

    1. Run short random walks starting from each node
    2. Nodes that frequently appear together in walks get similar embeddings
    3. Use Word2Vec (skip-gram) to learn d-dimensional vectors from these "sentences"

    **Two parameters control exploration**:

    | Parameter | Low value | High value |
    |-----------|-----------|------------|
    | **p** (return) | p < 1 → walks stay local (same community) | p > 1 → walks explore away |
    | **q** (in-out) | q < 1 → walks explore outward (DFS-like) | q > 1 → walks stay near (BFS-like) |

    **When to use**: Node classification, link prediction, visualization — any task where you need node features for an ML model.

    **Analogy**: Imagine walking randomly through a city. If you keep returning to the same block (low p), you learn about that neighborhood. If you always walk outward (low q), you learn the city's overall structure.
    """)
    return


@app.cell
def _(mo):
    mo.md("""
    ## Visualizing Node2Vec Embeddings

    Let's compute embeddings for the Karate Club and project them to 2D. Even in 2D, the embedding should separate the two factions.
    """)
    return


@app.cell
def _(Node2Vec, PCA, alt, mo, np, nx, pd, plt):
    G_emb = nx.karate_club_graph()

    node2vec = Node2Vec(G_emb, dimensions=64, walk_length=20, num_walks=50, workers=1, seed=42)
    model = node2vec.fit(window=10, min_count=1)

    embeddings = np.array([model.wv[str(n)] for n in G_emb.nodes()])

    pca = PCA(n_components=2)
    emb_2d = pca.fit_transform(embeddings)

    true_labels = [0 if G_emb.nodes[n]["club"] == "Mr. Hi" else 1 for n in G_emb.nodes()]

    _fig_emb, ax_emb = plt.subplots(figsize=(4, 4))
    colors_emb = ["#ff6b6b" if label == 0 else "#339af0" for label in true_labels]
    pos_original = nx.spring_layout(G_emb, seed=42)
    nx.draw_networkx_nodes(G_emb, pos_original, node_color=colors_emb, node_size=300, ax=ax_emb)
    nx.draw_networkx_edges(G_emb, pos_original, width=0.8, alpha=0.3, ax=ax_emb)
    ax_emb.set_title("Original Graph (colored by ground truth)", fontsize=13)
    ax_emb.axis("off")
    plt.tight_layout()
    mo.mpl.interactive(plt.gcf())

    _df = pd.DataFrame({
        "Node": list(G_emb.nodes()),
        "PC1": emb_2d[:, 0],
        "PC2": emb_2d[:, 1],
        "Community": ["Mr. Hi" if lb == 0 else "Officer" for lb in true_labels],
    })
    mo.ui.altair_chart(
        alt.Chart(_df)
        .mark_point(size=80, stroke="black", strokeWidth=0.5)
        .encode(
            x=alt.X("PC1", scale=alt.Scale(zero=False)),
            y=alt.Y("PC2", scale=alt.Scale(zero=False)),
            color=alt.Color(
                "Community:N",
                scale=alt.Scale(domain=["Mr. Hi", "Officer"], range=["#ff6b6b", "#339af0"]),
            ),
            tooltip=["Node", "PC1", "PC2", "Community"],
        )
        .properties(title="Node2Vec Embedding (PCA to 2D)", width=350, height=350)
        .interactive()
    )
    return emb_2d, true_labels


@app.cell
def _(emb_2d, mo, np, true_labels):
    from sklearn.linear_model import LogisticRegression
    from sklearn.model_selection import cross_val_score

    X = emb_2d
    y = np.array(true_labels)

    lr = LogisticRegression()
    scores = cross_val_score(lr, X, y, cv=5)

    mo.md(
        f"""
        **Can we predict which faction a node belongs to from just its 2D embedding?**

        Logistic Regression CV accuracy: **{scores.mean():.1%} ± {scores.std():.1%}**

        Even with just 2 dimensions, the embedding captures enough structure to predict community membership!
        """
    )
    return


@app.cell
def _(mo):
    mo.md("""
    ## Interactive: Explore Embedding Parameters

    Adjust the walk length, number of walks, and embedding dimensions to see how they affect the embedding quality.
    """)
    return


@app.cell
def _(mo):
    walk_len = mo.ui.slider(5, 50, step=5, value=20, label="Walk length")
    num_walks_slider = mo.ui.slider(10, 200, step=10, value=50, label="Number of walks per node")
    dims = mo.ui.slider(2, 128, step=2, value=16, label="Embedding dimensions")
    mo.hstack([walk_len, num_walks_slider, dims], gap=2)
    return dims, num_walks_slider, walk_len


@app.cell
def _(Node2Vec, PCA, alt, dims, mo, np, num_walks_slider, nx, pd, walk_len):
    G_int = nx.karate_club_graph()
    n2v_int = Node2Vec(
        G_int,
        dimensions=dims.value,
        walk_length=walk_len.value,
        num_walks=num_walks_slider.value,
        workers=1,
        seed=42,
        quiet=True,
    )
    model_int = n2v_int.fit(window=10, min_count=1)

    emb_int = np.array([model_int.wv[str(n)] for n in G_int.nodes()])
    pca_int = PCA(n_components=2)
    emb_2d_int = pca_int.fit_transform(emb_int)

    true_labs = [0 if G_int.nodes[n]["club"] == "Mr. Hi" else 1 for n in G_int.nodes()]

    _df = pd.DataFrame({
        "Node": list(G_int.nodes()),
        "PC1": emb_2d_int[:, 0],
        "PC2": emb_2d_int[:, 1],
        "Community": ["Mr. Hi" if lb == 0 else "Officer" for lb in true_labs],
    })

    mo.ui.altair_chart(
        alt.Chart(_df)
        .mark_point(size=100, stroke="black", strokeWidth=0.5)
        .encode(
            x=alt.X("PC1", scale=alt.Scale(zero=False)),
            y=alt.Y("PC2", scale=alt.Scale(zero=False)),
            color=alt.Color(
                "Community",
                scale=alt.Scale(domain=["Mr. Hi", "Officer"], range=["#ff6b6b", "#339af0"]),
            ),
            tooltip=["Node", "PC1", "PC2", "Community"],
        )
        .properties(
            title=f"Node2Vec (dim={dims.value}, walk={walk_len.value}, walks={num_walks_slider.value})",
            width=400,
            height=400,
        )
        .interactive()
    )
    return


@app.cell
def _(mo):
    mo.md("""
    # Part 2: Spectral Graph Theory

    Spectral graph theory studies graphs through the **eigenvalues and eigenvectors** of matrices derived from the graph (adjacency matrix, Laplacian).

    ## The Graph Laplacian

    $$L = D - A$$

    Where D is the degree matrix and A is the adjacency matrix.

    **Amazing properties**:
    - **Eigenvalue 0** always exists — its eigenvector is the constant vector (all 1s)
    - **Number of zero eigenvalues** = number of connected components in the graph
    - **Second smallest eigenvalue** (Fiedler eigenvalue) measures how well-connected the graph is
    - **Fiedler vector** (its eigenvector) gives a natural partition for spectral clustering

    > **Analogy**: The Laplacian spectrum is like the graph's "fingerprint" or "sound." Just as you can identify a musical chord by its frequencies, you can identify a graph's structure by its eigenvalues.
    """)
    return


@app.cell
def _(alt, mo, np, nx, pd, plt):
    G_spec = nx.karate_club_graph()

    L = nx.laplacian_matrix(G_spec).toarray()
    eigenvalues, eigenvectors = np.linalg.eigh(L)

    fiedler_vector = eigenvectors[:, 1]
    pos_spec = nx.spring_layout(G_spec, seed=42)
    n_eigen = min(15, len(eigenvalues))

    _fig1, ax1 = plt.subplots(figsize=(4, 3))
    colors_fiedler = plt.cm.coolwarm(
        (fiedler_vector - fiedler_vector.min()) / (fiedler_vector.max() - fiedler_vector.min() + 1e-10)
    )
    nx.draw_networkx_nodes(G_spec, pos_spec, node_color=colors_fiedler, node_size=200, ax=ax1)
    nx.draw_networkx_edges(G_spec, pos_spec, width=0.8, alpha=0.3, ax=ax1)
    ax1.set_title("Fiedler Vector", fontsize=11)
    ax1.axis("off")
    plt.tight_layout()
    mo.mpl.interactive(plt.gcf())

    df_spec = pd.DataFrame({
        "index": list(range(1, n_eigen + 1)),
        "eigenvalue": eigenvalues[:n_eigen],
    })
    mo.ui.altair_chart(
        alt.Chart(df_spec)
        .mark_line(point=True, color="#0077bb")
        .encode(
            x=alt.X("index", title="Eigenvalue index"),
            y=alt.Y("eigenvalue", title="Eigenvalue"),
            tooltip=["index", "eigenvalue"],
        )
        .properties(
            title=f"Laplacian Spectrum (first {n_eigen} eigenvalues)",
            width=300,
            height=250,
        )
        .interactive()
    )

    _fig2, ax2 = plt.subplots(figsize=(4, 3))
    fiedler_sign = fiedler_vector >= 0
    colors_cluster = ["#ff6b6b" if s else "#339af0" for s in fiedler_sign]
    nx.draw_networkx_nodes(G_spec, pos_spec, node_color=colors_cluster, node_size=200, ax=ax2)
    nx.draw_networkx_edges(G_spec, pos_spec, width=0.8, alpha=0.3, ax=ax2)
    ax2.set_title("Spectral Clustering (sign of Fiedler vector)", fontsize=11)
    ax2.axis("off")
    plt.tight_layout()
    mo.mpl.interactive(plt.gcf())
    return


@app.cell
def _(mo):
    mo.md("""
    **Key Insight**: The Fiedler vector naturally splits the graph into two communities — just by looking at the sign of each node's value! This is **spectral clustering**.

    Notice how this split matches what we found with community detection algorithms in the previous notebook. Spectral clustering is a different approach: instead of optimizing modularity, we find the optimal partition using the graph's Laplacian eigenvectors.

    **Why this works**: The Fiedler vector is the solution to the normalized cut problem — it finds the partition that minimizes the number of edges crossing between groups, relative to the group sizes.
    """)
    return


@app.cell
def _(mo):
    mo.md(r"""
    # Part 3: Graph Neural Networks (GNNs)

    GNNs are the state-of-the-art for learning on graphs. They work by **message passing**: nodes aggregate information from their neighbors.

    ## Message Passing Framework

    Each GNN layer does:
    1. **Message**: Each node sends its feature vector to all neighbors
    2. **Aggregate**: Each node collects messages from neighbors (sum, mean, max, or attention-weighted)
    3. **Update**: Each node combines its own features with the aggregated message through a neural network layer

    $$h_v^{{(k+1)}} = \sigma\left(W^{{(k)}} \cdot \text{{AGGREGATE}}\left(\{{h_u^{{(k)}} : u \in N(v)\}}, h_v^{{(k)}}\right)\right)$$

    After k layers, a node's representation contains information from its k-hop neighborhood.

    > **Analogy**: Your opinions are influenced by your friends (1 hop), their friends (2 hops), and so on. A 3-layer GNN captures "friends of friends of friends" influence.
    """)
    return


@app.cell
def _(mo):
    mo.md(r"""
    ## Common GNN Architectures

    | Architecture | Aggregation | Key Idea |
    |-------------|-------------|----------|
    | **GCN** (Graph Conv. Network) | Normalized sum | Simple and effective baseline |
    | **GAT** (Graph Attention) | Weighted sum (attention) | Learns which neighbors matter more |
    | **GraphSAGE** | Mean/Max/LSTM pooling | Scales to large graphs via neighbor sampling |
    | **GIN** (Graph Isomorphism) | Sum + MLP | Maximally expressive (distinguishes all graph structures) |

    ### GCN Layer Formula

    $$H^{{(k+1)}} = \sigma\left(\hat{{D}}^{{-1/2}} \hat{{A}} \hat{{D}}^{{-1/2}} H^{{(k)}} W^{{(k)}}\right)$$

    Where \(\hat{{A}} = A + I\) (adds self-loops so a node includes its own features) and \(\hat{{D}}\) is its degree matrix.

    The normalization \(\hat{{D}}^{{-1/2}} \hat{{A}} \hat{{D}}^{{-1/2}}\) ensures that high-degree nodes don't dominate the aggregation.

    **When to use GNNs**: Node classification, link prediction, graph classification, when you have node features and graph structure together.
    """)
    return


@app.cell
def _(mo):
    mo.md("""
    ## Simple GCN Implementation (Conceptual)

    ```python
    import torch
    import torch.nn as nn
    import torch.nn.functional as F

    class GCNLayer(nn.Module):
        def __init__(self, in_dim, out_dim):
            super().__init__()
            self.W = nn.Linear(in_dim, out_dim)

        def forward(self, X, A_hat, D_hat_inv_sqrt):
            # Normalized adjacency convolution
            conv = D_hat_inv_sqrt @ A_hat @ D_hat_inv_sqrt @ X
            return F.relu(self.W(conv))

    class GCN(nn.Module):
        def __init__(self, in_dim, hidden_dim, out_dim):
            super().__init__()
            self.layer1 = GCNLayer(in_dim, hidden_dim)
            self.layer2 = GCNLayer(hidden_dim, out_dim)

        def forward(self, X, A_hat, D_hat_inv_sqrt):
            h = self.layer1(X, A_hat, D_hat_inv_sqrt)
            return self.layer2(h, A_hat, D_hat_inv_sqrt)
    ```

    This 2-layer GCN does:
    1. **Layer 1**: Each node aggregates features from its immediate neighbors → hidden representation
    2. **Layer 2**: Each node aggregates hidden representations from its neighbors → output (e.g., class predictions)

    > **Note**: Installing PyTorch is beyond the scope of this notebook, but the concepts are what matter. See PyTorch Geometric (PyG) for production-ready GNN implementations.
    """)
    return


@app.cell
def _(mo):
    mo.md("""
    # Part 4: Knowledge Graphs

    **Knowledge graphs** extend simple graphs with **types** and **properties**:
    - Nodes have **labels** (Person, Company, City)
    - Edges have **types** (works_at, lives_in, founded)
    - Nodes and edges have **properties** (name, age, founded_date)

    > **Analogy**: A simple graph says "Alice → Bob" (friend). A knowledge graph says "Alice (Person, age 30) — works_at → Acme Corp (Company, founded 2010)."

    This is the foundation of:
    - **Google Knowledge Graph** (info boxes in search results)
    - **Wikidata / DBpedia**
    - **Neo4j** graph databases
    - **Enterprise knowledge management**
    - **RAG (Retrieval-Augmented Generation)** systems
    """)
    return


@app.cell
def _(mo, np, nx, plt):
    KG = nx.MultiDiGraph()

    KG.add_node("Alice", type="Person", age=30)
    KG.add_node("Bob", type="Person", age=28)
    KG.add_node("Acme Corp", type="Company", founded=2010)
    KG.add_node("Wellington", type="City", country="NZ")

    KG.add_edge("Alice", "Acme Corp", key="works_at", role="Engineer")
    KG.add_edge("Bob", "Acme Corp", key="works_at", role="Designer")
    KG.add_edge("Alice", "Wellington", key="lives_in")
    KG.add_edge("Acme Corp", "Wellington", key="located_in")
    KG.add_edge("Alice", "Bob", key="knows")
    KG.add_edge("Bob", "Alice", key="knows")

    _fig_kg, ax_kg = plt.subplots(figsize=(7, 5))
    pos_kg = nx.spring_layout(KG.to_undirected(), seed=42)

    node_colors_type = []
    sizes_kg = []
    for _n in KG.nodes():
        if KG.nodes[_n]["type"] == "Person":
            node_colors_type.append("#ff6b6b")
            sizes_kg.append(1500)
        elif KG.nodes[_n]["type"] == "Company":
            node_colors_type.append("#339af0")
            sizes_kg.append(2000)
        else:
            node_colors_type.append("#51cf66")
            sizes_kg.append(1500)

    nx.draw_networkx_nodes(KG, pos_kg, node_color=node_colors_type, node_size=sizes_kg, ax=ax_kg)
    nx.draw_networkx_labels(KG, pos_kg, font_size=11, font_weight="bold", ax=ax_kg)

    type_labels = {n: f"{n}\\n({KG.nodes[n]['type']})" for n in KG.nodes()}
    label_pos = {n: (pos_kg[n][0], pos_kg[n][1] - 0.08) for n in KG.nodes()}
    nx.draw_networkx_labels(KG, label_pos, labels=type_labels, font_size=9, font_color="gray", ax=ax_kg)

    for u, v, k, _d in KG.edges(data=True, keys=True):
        ax_kg.annotate(
            "",
            xy=pos_kg[v],
            xytext=pos_kg[u],
            arrowprops={"arrowstyle": "->", "color": "gray", "lw": 1.5, "connectionstyle": "arc3,rad=0.2"},
        )
        mid = ((pos_kg[u][0] + pos_kg[v][0]) / 2, (pos_kg[u][1] + pos_kg[v][1]) / 2)
        angle = np.arctan2(pos_kg[v][1] - pos_kg[u][1], pos_kg[v][0] - pos_kg[u][0])
        offset = 0.06
        mid2 = (mid[0] + offset * np.sin(angle), mid[1] - offset * np.cos(angle))
        ax_kg.text(
            mid2[0],
            mid2[1],
            k,
            fontsize=8,
            color="gray",
            bbox={"facecolor": "white", "edgecolor": "none", "alpha": 0.7},
            ha="center",
        )

    ax_kg.set_title("A Simple Knowledge Graph", fontsize=14)
    ax_kg.axis("off")
    plt.tight_layout()
    mo.mpl.interactive(plt.gcf())
    return


@app.cell
def _(mo):
    mo.md("""
    # Part 5: Where to Go Next

    ## Congratulations!

    You've completed the Graph Workshop! Here's your roadmap for further learning.

    ### 📚 Books
    - **"Networks: An Introduction"** by Mark Newman — the definitive textbook
    - **"Network Science"** by Albert-László Barabási — free online at networksciencebook.com
    - **"Graph Representation Learning"** by William L. Hamilton — modern ML on graphs

    ### 🛠️ Libraries to Explore
    - **NetworkX** — general graph analysis (what we used)
    - **igraph** — faster C-based graph library
    - **PyTorch Geometric (PyG)** — GNNs in PyTorch
    - **DGL (Deep Graph Library)** — GNNs in PyTorch/TensorFlow
    - **Neo4j** — graph database for production systems
    - **CuGraph** — GPU-accelerated graph analytics

    ### 🔬 Open Research Areas
    - **Temporal graphs** — networks that change over time
    - **Heterogeneous graphs** — multiple node/edge types
    - **Graph generation** — creating realistic synthetic graphs
    - **Explainability** — understanding why a GNN made a prediction
    - **Scaling GNNs** — billion-node graphs
    """)
    return


@app.cell
def _(mo):
    mo.md("""
    ## Workshop Summary

    | Notebook | Topic | Key Concepts |
    |----------|-------|-------------|
    | [01](./01_graph_foundations.py) | **Graph Foundations** | Nodes, edges, degree, graph types |
    | [02](./02_graph_representation.py) | **Graph Representation** | Adj. matrix, adj. list, visualization, graph models |
    | [03](./03_graph_traversal.py) | **Graph Traversal** | BFS, DFS, shortest path, Dijkstra, connected components |
    | [04](./04_centrality.py) | **Centrality & Influence** | Degree, betweenness, closeness, eigenvector, PageRank |
    | [05](./05_communities.py) | **Communities & Clustering** | Modularity, Greedy Modularity, Label Propagation |
    | [06](./06_advanced_topics.py) | **Advanced Topics** | Node2Vec, spectral theory, GNNs, knowledge graphs |

    **Happy graphing!** The world is made of connections — now you have the tools to understand and analyze them.
    """)
    return


if __name__ == "__main__":
    app.run()
