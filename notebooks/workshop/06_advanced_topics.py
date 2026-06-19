# ---
# marimo-version: 0.23.9
# license: Apache-2.0
# ---

import marimo

__generated_with = "0.23.9"
app = marimo.App(width="full")


@app.cell
def _():
    import networkx as nx
    import matplotlib.pyplot as plt
    import numpy as np
    import marimo as mo
    from sklearn.decomposition import PCA
    from sklearn.manifold import TSNE
    from node2vec import Node2Vec
    import warnings
    warnings.filterwarnings("ignore")
    return Node2Vec, PCA, mo, np, nx, plt


@app.cell
def _(mo):
    mo.md("""
    # Advanced Topics: Graph Embeddings, Spectral Methods & GNNs

    Welcome to the final notebook! We've covered foundations, traversal, centrality, and communities. Now let's look at modern, cutting-edge graph techniques.

    ## What We'll Cover

    1. **Graph Embeddings** — Turning nodes into vectors (Node2Vec)
    2. **Spectral Graph Theory** — What eigenvalues tell us about graphs
    3. **Graph Neural Networks (GNNs)** — Deep learning on graphs
    4. **Knowledge Graphs** — Beyond simple networks
    5. **Where to Go Next**
    """)
    return


@app.cell
def _(mo):
    mo.md("""
    # Part 1: Graph Embeddings

    ## Why Embeddings?

    Most machine learning algorithms work on **vectors** (tables of numbers), not graphs directly. **Graph embeddings** convert nodes, edges, or entire graphs into dense vector representations while preserving structural properties.

    > A good embedding puts similar nodes close together in vector space.
    """)
    return


@app.cell
def _(mo):
    mo.md("""
    ## Node2Vec: Biased Random Walks

    **Node2Vec** learns embeddings by simulating random walks on the graph and treating them like sentences in Word2Vec.

    **Key idea**: Run short random walks from each node. Nodes that frequently appear together in walks should have similar embeddings.

    Two parameters control the walk behavior:
    - **\(p\)** (Return parameter): probability of revisiting a node
    - **\(q\)** (In-out parameter): balance between BFS-like and DFS-like exploration

    $$p < 1$$ → walks stay local (homophily — same community)
    $$q < 1$$ → walks explore outward (structural equivalence — same role)
    """)
    return


@app.cell
def _(mo):
    mo.md("""
    ## Visualizing Node2Vec Embeddings

    Let's compute embeddings for the Karate Club and project them to 2D:
    """)
    return


@app.cell
def _(Node2Vec, PCA, mo, np, nx, plt):
    G_emb = nx.karate_club_graph()

    node2vec = Node2Vec(G_emb, dimensions=64, walk_length=20, num_walks=50, workers=1, seed=42)
    model = node2vec.fit(window=10, min_count=1)

    embeddings = np.array([model.wv[str(n)] for n in G_emb.nodes()])

    pca = PCA(n_components=2)
    emb_2d = pca.fit_transform(embeddings)

    true_labels = [0 if G_emb.nodes[n]["club"] == "Mr. Hi" else 1 for n in G_emb.nodes()]

    fig_emb, (ax_emb1, ax_emb2) = plt.subplots(1, 2, figsize=(18, 7))

    colors_emb = ["#ff6b6b" if l == 0 else "#339af0" for l in true_labels]

    pos_original = nx.spring_layout(G_emb, seed=42)
    nx.draw_networkx_nodes(G_emb, pos_original, node_color=colors_emb, node_size=300, ax=ax_emb1)
    nx.draw_networkx_edges(G_emb, pos_original, width=0.8, alpha=0.3, ax=ax_emb1)
    ax_emb1.set_title("Original Graph (colored by ground truth)", fontsize=13)
    ax_emb1.axis("off")

    for i, n in enumerate(G_emb.nodes()):
        ax_emb2.scatter(emb_2d[i, 0], emb_2d[i, 1], c=colors_emb[i], s=150, edgecolors="black", linewidths=0.5, zorder=5)
        ax_emb2.annotate(str(n), (emb_2d[i, 0], emb_2d[i, 1]), fontsize=9, ha="center", va="bottom")

    ax_emb2.set_title("Node2Vec Embedding (PCA to 2D)", fontsize=13)
    ax_emb2.set_xlabel("PC1")
    ax_emb2.set_ylabel("PC2")
    ax_emb2.grid(alpha=0.3)

    plt.tight_layout()
    mo.mpl.interactive(plt.gcf())
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
def _(Node2Vec, PCA, dims, mo, np, num_walks_slider, nx, plt, walk_len):
    G_int = nx.karate_club_graph()
    n2v_int = Node2Vec(G_int, dimensions=dims.value, walk_length=walk_len.value, num_walks=num_walks_slider.value, workers=1, seed=42, quiet=True)
    model_int = n2v_int.fit(window=10, min_count=1, quiet=True)

    emb_int = np.array([model_int.wv[str(n)] for n in G_int.nodes()])
    pca_int = PCA(n_components=2)
    emb_2d_int = pca_int.fit_transform(emb_int)

    fig_int, ax_int = plt.subplots(figsize=(10, 7))
    true_labs = [0 if G_int.nodes[n]["club"] == "Mr. Hi" else 1 for n in G_int.nodes()]
    colors_int = ["#ff6b6b" if l == 0 else "#339af0" for l in true_labs]
    ax_int.scatter(emb_2d_int[:, 0], emb_2d_int[:, 1], c=colors_int, s=200, edgecolors="black", linewidths=0.5)
    for i, n in enumerate(G_int.nodes()):
        ax_int.annotate(str(n), (emb_2d_int[i, 0], emb_2d_int[i, 1]), fontsize=9, ha="center", va="bottom")
    ax_int.set_title(f"Node2Vec (dim={dims.value}, walk={walk_len.value}, walks={num_walks_slider.value})", fontsize=13)
    ax_int.set_xlabel("PC1")
    ax_int.set_ylabel("PC2")
    ax_int.grid(alpha=0.3)
    plt.tight_layout()
    mo.mpl.interactive(plt.gcf())
    return


@app.cell
def _(mo):
    mo.md("""
    # Part 2: Spectral Graph Theory

    Spectral graph theory studies graphs through the **eigenvalues and eigenvectors** of matrices derived from the graph (adjacency matrix, Laplacian).

    ## The Graph Laplacian

    $$L = D - A$$

    Where \(D\) is the degree matrix and \(A\) is the adjacency matrix.

    The Laplacian has amazing properties:
    - **Eigenvalue 0** always exists — its eigenvector is the constant vector
    - **Number of zero eigenvalues** = number of connected components
    - **Second smallest eigenvalue** (Fiedler eigenvalue) measures graph connectivity
    - **Fiedler vector** (its eigenvector) provides a spectral clustering partition
    """)
    return


@app.cell
def _(mo, np, nx, plt):
    G_spec = nx.karate_club_graph()

    L = nx.laplacian_matrix(G_spec).toarray()
    eigenvalues, eigenvectors = np.linalg.eigh(L)

    fiedler_vector = eigenvectors[:, 1]

    fig_spec, axes_spec = plt.subplots(1, 3, figsize=(20, 6))
    pos_spec = nx.spring_layout(G_spec, seed=42)

    colors_fiedler = plt.cm.coolwarm((fiedler_vector - fiedler_vector.min()) / (fiedler_vector.max() - fiedler_vector.min() + 1e-10))
    nx.draw_networkx_nodes(G_spec, pos_spec, node_color=colors_fiedler, node_size=300, ax=axes_spec[0])
    nx.draw_networkx_edges(G_spec, pos_spec, width=0.8, alpha=0.3, ax=axes_spec[0])
    axes_spec[0].set_title("Fiedler Vector (color = spectral sign)", fontsize=13)
    axes_spec[0].axis("off")

    n_eigen = min(15, len(eigenvalues))
    axes_spec[1].plot(range(1, n_eigen + 1), eigenvalues[:n_eigen], "bo-", markersize=8)
    axes_spec[1].axhline(y=0, color="gray", linestyle="--", alpha=0.5)
    axes_spec[1].set_xlabel("Eigenvalue index")
    axes_spec[1].set_ylabel("Eigenvalue")
    axes_spec[1].set_title("Laplacian Spectrum (first {} eigenvalues)".format(n_eigen))
    axes_spec[1].grid(alpha=0.3)

    fiedler_sign = fiedler_vector >= 0
    colors_cluster = ["#ff6b6b" if s else "#339af0" for s in fiedler_sign]
    nx.draw_networkx_nodes(G_spec, pos_spec, node_color=colors_cluster, node_size=300, ax=axes_spec[2])
    nx.draw_networkx_edges(G_spec, pos_spec, width=0.8, alpha=0.3, ax=axes_spec[2])
    axes_spec[2].set_title("Spectral Clustering (sign of Fiedler vector)", fontsize=13)
    axes_spec[2].axis("off")

    plt.tight_layout()
    mo.mpl.interactive(plt.gcf())
    return


@app.cell
def _(mo):
    mo.md(f"""
    **Key Insight**: The Fiedler vector naturally splits the graph into two communities — just by looking at the sign of each node's value! This is **spectral clustering**.

    Notice how this split matches what we found with community detection algorithms in the previous notebook.
    """)
    return


@app.cell
def _(mo):
    mo.md("""
    # Part 3: Graph Neural Networks (GNNs)

    GNNs are the state-of-the-art for learning on graphs. They work by **message passing**: nodes aggregate information from their neighbors.

    ## Message Passing Framework

    Each GNN layer does:
    1. **Message**: Each node sends its feature vector to neighbors
    2. **Aggregate**: Each node collects messages from neighbors (sum, mean, max)
    3. **Update**: Each node combines its own features with the aggregated message

    $$h_v^{(k+1)} = \sigma\left(W^{(k)} \cdot 	ext{AGGREGATE}\left(\{h_u^{(k)} : u \in N(v)\}, h_v^{(k)}
    ight)
    ight)$$

    After \(k\) layers, a node's representation contains information from its \(k\)-hop neighborhood.
    """)
    return


@app.cell
def _(mo):
    mo.md("""
    ## Common GNN Architectures

    | Architecture | Aggregation | Key Idea |
    |-------------|-------------|----------|
    | **GCN** (Graph Conv. Network) | Normalized sum | Simple and effective |
    | **GAT** (Graph Attention) | Weighted sum (attention) | Learns which neighbors matter more |
    | **GraphSAGE** | Mean/Max/LSTM pooling | Scales to large graphs via sampling |
    | **GIN** (Graph Isomorphism) | Sum + MLP | Maximally expressive |

    ### GCN Layer Formula
    $$H^{(k+1)} = \sigma\left(\hat{D}^{-1/2} \hat{A} \hat{D}^{-1/2} H^{(k)} W^{(k)}
    ight)$$

    Where \(\hat{A} = A + I\) (adds self-loops) and \(\hat{D}\) is its degree matrix.
    """)
    return


@app.cell
def _(mo):
    mo.md("""
    ## Simple GNN with PyTorch (Conceptual)

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

    This is the essence of a 2-layer GCN — stack two message-passing layers and classify nodes!

    > **Note**: Installing PyTorch is beyond the scope of this notebook, but the concepts are what matter.
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

    ## Example: A Tiny Knowledge Graph

    ```
    (Alice) —[works_at]→ (Acme Corp)
    (Alice) —[lives_in]→ (Wellington)
    (Acme Corp) —[located_in]→ (Wellington)
    (Bob) —[works_at]→ (Acme Corp)
    ```

    This is the foundation of:
    - **Google Knowledge Graph** (the info boxes in search results)
    - **Wikidata / DBpedia**
    - **Neo4j** graph databases
    - **Enterprise knowledge management**
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

    fig_kg, ax_kg = plt.subplots(figsize=(12, 8))
    pos_kg = nx.spring_layout(KG.to_undirected(), seed=42)

    node_colors_type = []
    sizes_kg = []
    for n in KG.nodes():
        if KG.nodes[n]["type"] == "Person":
            node_colors_type.append("#ff6b6b")
            sizes_kg.append(1500)
        elif KG.nodes[n]["type"] == "Company":
            node_colors_type.append("#339af0")
            sizes_kg.append(2000)
        else:
            node_colors_type.append("#51cf66")
            sizes_kg.append(1500)

    nx.draw_networkx_nodes(KG, pos_kg, node_color=node_colors_type, node_size=sizes_kg, ax=ax_kg)
    nx.draw_networkx_labels(KG, pos_kg, font_size=11, font_weight="bold", ax=ax_kg)

    type_labels = {n: f"{n}\n({KG.nodes[n]['type']})" for n in KG.nodes()}
    label_pos = {n: (pos_kg[n][0], pos_kg[n][1] - 0.08) for n in KG.nodes()}
    nx.draw_networkx_labels(KG, label_pos, labels=type_labels, font_size=9, font_color="gray", ax=ax_kg)

    for u, v, k, d in KG.edges(data=True, keys=True):
        ax_kg.annotate(
            "", xy=pos_kg[v], xytext=pos_kg[u],
            arrowprops=dict(arrowstyle="->", color="gray", lw=1.5, connectionstyle="arc3,rad=0.2"),
        )
        mid = ((pos_kg[u][0] + pos_kg[v][0]) / 2, (pos_kg[u][1] + pos_kg[v][1]) / 2)
        angle = np.arctan2(pos_kg[v][1] - pos_kg[u][1], pos_kg[v][0] - pos_kg[u][0])
        offset = 0.06
        mid2 = (mid[0] + offset * np.sin(angle), mid[1] - offset * np.cos(angle))
        ax_kg.text(mid2[0], mid2[1], k, fontsize=8, color="gray",
                   bbox=dict(facecolor="white", edgecolor="none", alpha=0.7), ha="center")

    ax_kg.set_title("A Simple Knowledge Graph", fontsize=14)
    ax_kg.axis("off")
    plt.tight_layout()
    mo.mpl.interactive(plt.gcf())
    return


@app.cell
def _(mo):
    mo.md("""
    # Part 5: Where to Go Next

    ## Congratulations! 🎉

    You've completed the Graph Workshop! Here's your roadmap for further learning:

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

    ### 🎯 Practice Projects
    1. Analyze your own social network (Twitter, LinkedIn connections)
    2. Build a recommendation system using graph algorithms
    3. Analyze a transportation network (find critical roads)
    4. Detect fraud using community detection
    5. Build a knowledge graph from Wikipedia data

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
    | 1 | **Graph Foundations** | Nodes, edges, degree, graph types |
    | 2 | **Graph Representation** | Adj. matrix, adj. list, visualization, graph models |
    | 3 | **Graph Traversal** | BFS, DFS, shortest path, Dijkstra, connected components |
    | 4 | **Centrality & Influence** | Degree, betweenness, closeness, eigenvector, PageRank |
    | 5 | **Communities & Clustering** | Modularity, Greedy Modularity, Label Propagation, spectral clustering |
    | 6 | **Advanced Topics** | Node2Vec, spectral theory, GNNs, knowledge graphs |

    **Happy graphing!** The world is made of connections — now you have the tools to understand them.
    """)
    return


@app.cell
def _():
    return


if __name__ == "__main__":
    app.run()
