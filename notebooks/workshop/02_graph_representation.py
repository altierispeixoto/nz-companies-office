# ---
# marimo-version: 0.23.9
# license: Apache-2.0
# ---

import marimo

__generated_with = "0.23.10"
app = marimo.App(width="full")


@app.cell
def _():
    import marimo as mo
    import matplotlib.pyplot as plt
    import networkx as nx
    import numpy as np

    return mo, np, nx, plt


@app.cell
def _(mo):
    mo.md("""
    # 02 — Graph Representation & Visualization

    We know *what* a graph is. Now let's understand *how* graphs are stored inside a computer and explore different ways to visualize them.

    | # | Topic | What You'll Learn |
    |---|-------|-------------------|
    | 1 | **Why Representation Matters** | Memory, speed, and algorithm trade-offs |
    | 2 | **Three Main Representations** | Edge list vs adjacency list vs adjacency matrix |
    | 3 | **Real-World: Karate Club** | See sparsity in action |
    | 4 | **Graph Models** | Random, preferential attachment, small-world |
    | 5 | **Interactive Model Explorer** | Compare models side-by-side |
    | 6 | **Graph Layouts** | Different visual perspectives |

    ---

    > **Analogy**: Describing a road network as a list of connected intersections (edge list) vs a matrix with rows/columns for every intersection (adjacency matrix) — both are correct, but one is far more practical.
    """)
    return


@app.cell
def _(mo):
    mo.md("""
    ## Topic 1: Why Representation Matters

    The way we store a graph affects everything:

    | Factor | Edge List | Adjacency List | Adjacency Matrix |
    |--------|-----------|---------------|------------------|
    | **Memory** | O(E) | O(V + E) | O(V²) |
    | **Check connection** | O(E) — scan all edges | O(deg(v)) — scan neighbors | O(1) — matrix lookup |
    | **Find all neighbors** | O(E) — scan all edges | O(1) — direct lookup | O(V) — scan row |
    | **Add edge** | O(1) — append | O(1) — append | O(1) — set entry |
    | **Best for** | Simple storage | Most graph algorithms | Dense graphs, linear algebra |

    > **Key insight**: Real-world graphs are **sparse** — way fewer edges than possible (|E| << |V|²). An adjacency matrix for the Facebook graph would have 10¹⁶ entries (impossible). An adjacency list? ~10¹¹ (manageable with distributed systems).
    """)
    return


@app.cell
def _(mo):
    mo.md("""
    ## Topic 2: The Three Main Representations

    ### 1. Edge List — The Simplest

    Just list every edge as a pair `(u, v)`:

    ```
    [("Alice", "Bob"), ("Alice", "Charlie"), ("Bob", "Charlie"), ("Charlie", "Diana")]
    ```

    **How it works**: Each row is one relationship. To find Alice's friends, scan the whole list.

    > **When to use**: File storage, data exchange formats. Not for algorithms.

    ### 2. Adjacency List — The Workhorse

    For each node, store a list of its neighbors:

    ```
    Alice:   [Bob, Charlie]
    Bob:     [Alice, Charlie]
    Charlie: [Alice, Bob, Diana]
    Diana:   [Charlie]
    ```

    **How it works**: Dictionary/hash map from node → list of neighbors. Finding Alice's friends? Direct lookup.

    > **When to use**: Default choice for almost all graph algorithms (BFS, DFS, Dijkstra, PageRank).

    ### 3. Adjacency Matrix — The Math Tool

    An n×n matrix where entry A[i][j] = 1 if there's an edge from i to j:

    ```
        Alice Bob Charlie Diana
    Alice  0    1     1      0
    Bob    1    0     1      0
    Charlie 1   1     0      1
    Diana  0    0     1      0
    ```

    **How it works**: Direct row/column indexing. Powers of A give path counts (A²[i][j] = number of length-2 paths from i to j).

    > **When to use**: Spectral analysis, algebraic graph theory, dense graphs, GPU computation.
    """)
    return


@app.cell
def _(mo, nx):
    G = nx.karate_club_graph()

    adj_matrix = nx.to_numpy_array(G)

    mo.md(
        f"""
        ## Topic 3: Real-World Comparison — Zachary's Karate Club

        We'll use a famous real-world graph: **Zachary's Karate Club** — 34 members of a university karate club.

        | Metric | Value |
        |--------|-------|
        | Nodes | {G.number_of_nodes()} |
        | Edges | {G.number_of_edges()} |
        | Adj. Matrix Size | {adj_matrix.shape[0]} × {adj_matrix.shape[1]} = {adj_matrix.shape[0] * adj_matrix.shape[1]} entries |
        | Non-zero entries | {int(adj_matrix.sum())} (only {int(adj_matrix.sum()) / (adj_matrix.shape[0] * adj_matrix.shape[1]) * 100:.1f}% filled) |

        Notice how **sparse** the adjacency matrix is — less than 10% filled! That's why adjacency lists are the default.

        > **Analogy**: An adjacency matrix for a city's road network would be a spreadsheet with a row/column for every address, but only 0.001% of cells have a road. The adjacency list is just a map of "this address connects to these addresses."
        """
    )
    return (G,)


@app.cell
def _(G, mo, np, nx, plt):
    fig, axes = plt.subplots(1, 3, figsize=(18, 5))

    pos = nx.spring_layout(G, seed=42)

    nx.draw_networkx_nodes(G, pos, node_color="lightblue", node_size=200, ax=axes[0])
    nx.draw_networkx_edges(G, pos, width=0.5, alpha=0.5, ax=axes[0])
    axes[0].set_title("Graph Visualization", fontsize=13)
    axes[0].axis("off")

    adj = nx.to_numpy_array(G)
    im = axes[1].imshow(adj, cmap="Blues", interpolation="none")
    axes[1].set_title(f"Adjacency Matrix ({adj.shape[0]}×{adj.shape[1]})", fontsize=13)
    axes[1].set_xlabel("Node")
    axes[1].set_ylabel("Node")
    plt.colorbar(im, ax=axes[1], shrink=0.8)

    degrees = [d for _, d in G.degree()]
    axes[2].hist(degrees, bins=15, color="steelblue", edgecolor="white", alpha=0.7)
    axes[2].axvline(np.mean(degrees), color="red", linestyle="--", label=f"Mean: {np.mean(degrees):.1f}")
    axes[2].set_xlabel("Degree")
    axes[2].set_ylabel("Frequency")
    axes[2].set_title("Degree Distribution", fontsize=13)
    axes[2].legend()

    plt.tight_layout()
    mo.mpl.interactive(plt.gcf())
    return


@app.cell
def _(mo):
    mo.md("""
    ## Topic 4: Graph Models

    Random graph models help us understand what real networks look like by comparison. Each model captures different structural properties:

    ### 🎲 Erdos-Renyi (Random)

    Every pair of nodes has probability p of being connected.

    - **How it works**: Flip a biased coin for each potential edge
    - **Degree distribution**: Poisson (bell-shaped) — most nodes have similar degree
    - **Realism**: Low — real networks aren't this random
    - **When to use**: Null model for statistical tests, mathematical tractability

    **Analogy**: A party where everyone randomly meets everyone else with the same probability.

    ### 🌟 Barabasi-Albert (Preferential Attachment)

    New nodes connect to existing nodes with probability proportional to their degree ("the rich get richer").

    - **How it works**: Start with a small graph. Add nodes one by one. Each new node picks m neighbors weighted by degree.
    - **Degree distribution**: Power law — few hubs, many low-degree nodes
    - **Realism**: High — the internet, social networks, and citation networks follow this pattern
    - **When to use**: Modeling growth processes, scale-free networks

    **Analogy**: A new Twitter user follows the celebrities everyone else follows (high-degree nodes).

    ### 🔗 Watts-Strogatz (Small World)

    Start with a regular ring lattice, then randomly rewire some edges.

    - **How it works**: Each node connects to k nearest neighbors in a ring. Then rewire each edge with probability p.
    - **Key property**: High clustering (friends know each other) + short paths (six degrees)
    - **Realism**: High — social networks exhibit this "small world" phenomenon
    - **When to use**: Modeling social networks, disease spread

    **Analogy**: Your friends likely know each other (high clustering), yet you're only a few introductions away from anyone in the world (short paths).
    """)
    return


@app.cell
def _(mo):
    graph_type = mo.ui.dropdown(
        ["Erdos-Renyi (Random)", "Barabasi-Albert (Preferential Attachment)", "Watts-Strogatz (Small World)"],
        value="Erdos-Renyi (Random)",
        label="Choose a graph model:",
    )
    graph_type
    return (graph_type,)


@app.cell
def _(graph_type, mo, np, nx, plt):
    n = 50

    if "Erdos" in graph_type.value:
        p = 0.08
        G_model = nx.erdos_renyi_graph(n, p, seed=42)
        model_name = f"Erdos-Renyi (n={n}, p={p})"
    elif "Barabasi" in graph_type.value:
        m = 2
        G_model = nx.barabasi_albert_graph(n, m, seed=42)
        model_name = f"Barabasi-Albert (n={n}, m={m})"
    else:
        k = 4
        p_rewire = 0.3
        G_model = nx.watts_strogatz_graph(n, k, p_rewire, seed=42)
        model_name = f"Watts-Strogatz (n={n}, k={k}, p={p_rewire})"

    fig_model, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 5))

    pos_model = nx.spring_layout(G_model, seed=42, iterations=50)
    nx.draw_networkx_nodes(G_model, pos_model, node_size=50, node_color="lightblue", alpha=0.7, ax=ax1)
    nx.draw_networkx_edges(G_model, pos_model, width=0.3, alpha=0.3, ax=ax1)
    ax1.set_title(model_name)
    ax1.axis("off")

    degs = [d for _, d in G_model.degree()]
    ax2.hist(degs, bins=20, color="steelblue", edgecolor="white", alpha=0.7)
    ax2.axvline(np.mean(degs), color="red", linestyle="--", label=f"Mean: {np.mean(degs):.1f}")
    ax2.set_xlabel("Degree")
    ax2.set_ylabel("Frequency")
    ax2.set_title("Degree Distribution")
    ax2.legend()

    plt.tight_layout()
    mo.mpl.interactive(plt.gcf())
    return (G_model,)


@app.cell
def _(G_model, mo, nx, plt):
    fig_props, (ax_p, ax_s) = plt.subplots(1, 2, figsize=(14, 4))

    props = {
        "Nodes": G_model.number_of_nodes(),
        "Edges": G_model.number_of_edges(),
        "Avg. Degree": f"{sum(d for _, d in G_model.degree()) / G_model.number_of_nodes():.1f}",
        "Density": f"{nx.density(G_model):.4f}",
        "Avg. Clustering": f"{nx.average_clustering(G_model):.3f}",
        "Is Connected": nx.is_connected(G_model),
    }

    ax_p.axis("off")
    y = 0.9
    for key, val in props.items():
        ax_p.text(0.1, y, f"{key}: {val}", fontsize=13, transform=ax_p.transAxes)
        y -= 0.12

    degree_sequence = sorted([d for _, d in G_model.degree()], reverse=True)
    ax_s.plot(degree_sequence, "b.-", alpha=0.7)
    ax_s.set_xlabel("Nodes (ranked by degree)")
    ax_s.set_ylabel("Degree")
    ax_s.set_title("Degree Rank Plot (sorted descending)")
    ax_s.grid(True, alpha=0.3)

    plt.tight_layout()
    mo.mpl.interactive(plt.gcf())
    return


@app.cell
def _(mo):
    mo.md("""
    ## Topic 5: Graph Layouts — Seeing Different Structures

    How we position nodes visually matters. Different layout algorithms reveal different aspects:

    | Layout | How It Works | When to Use |
    |--------|-------------|-------------|
    | **Spring (force-directed)** | Simulates physics — nodes repel, edges attract | General purpose, reveals clusters |
    | **Circular** | Nodes arranged in a circle | Ring structures, periodic data |
    | **Kamada-Kawai** | Minimizes energy between all node pairs | Large graphs, needs speed |
    | **Spectral** | Uses eigenvectors of Laplacian | Reveals spectral structure, connects to theory |

    > **Analogy**: The same social network can look like a hairball (force-directed), a merry-go-round (circular), or reveal hidden factions (spectral). The layout is a lens, not the graph itself.
    """)
    return


@app.cell
def _(G_model, mo, nx, plt):
    layouts = {
        "Spring (force-directed)": nx.spring_layout(G_model, seed=42, iterations=50),
        "Circular": nx.circular_layout(G_model),
        "Kamada-Kawai": nx.kamada_kawai_layout(G_model),
        "Spectral": nx.spectral_layout(G_model),
    }

    fig_layout, axes_layout = plt.subplots(2, 2, figsize=(20, 20))
    for (name, pos_layout), ax in zip(layouts.items(), axes_layout.flat):
        nx.draw_networkx_nodes(G_model, pos_layout, node_size=30, node_color="lightblue", alpha=0.7, ax=ax)
        nx.draw_networkx_edges(G_model, pos_layout, width=0.3, alpha=0.3, ax=ax)
        ax.set_title(name, fontsize=13)
        ax.axis("off")

    plt.tight_layout()
    mo.mpl.interactive(plt.gcf())
    return


@app.cell
def _(mo):
    mo.md("""
    ## Summary

    | # | You've Learned | Key Insight |
    |---|---------------|-------------|
    | 1 | **Why representation matters** | Memory, speed, and algorithm choice depend on the format |
    | 2 | **Three representations** | Edge list (simple), adjacency list (default), adjacency matrix (math) |
    | 3 | **Sparsity** | Real graphs are sparse — adjacency matrix has < 10% non-zero entries |
    | 4 | **Graph models** | Random, preferential attachment, and small-world capture different properties |
    | 5 | **Layouts** | Each layout algorithm reveals a different structural perspective |

    **Next up:** [03 — Graph Traversal](./03_graph_traversal.py) — BFS, DFS, finding paths, and exploring connected components.
    """)
    return


if __name__ == "__main__":
    app.run()
