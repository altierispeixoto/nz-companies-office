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
    from scipy.sparse import csr_matrix

    return mo, np, nx, plt


@app.cell
def _(mo):
    mo.md("""
    # Graph Representation & Visualization

    In the previous notebook, we learned *what* a graph is. Now let's understand *how* graphs are stored in a computer and explore different ways to visualize them.

    ## Why Does Representation Matter?

    The way we store a graph affects:
    - **Memory usage** — how much RAM we need
    - **Speed** — how fast we can traverse or query the graph
    - **Algorithm choice** — some algorithms work better with certain representations
    """)
    return


@app.cell
def _(mo):
    mo.md("""
    ## The Three Main Representations

    ### 1. Edge List
    The simplest format: just list all edges as pairs `(u, v)`.

    ```
    [(Alice, Bob), (Alice, Charlie), (Bob, Charlie), (Charlie, Diana)]
    ```

    ✅ Simple and space-efficient for sparse graphs
    ❌ Slow to check if two nodes are connected (\(\mathcal{O}(|E|)\))

    ### 2. Adjacency List
    For each node, store a list of its neighbors.

    ```
    Alice:   [Bob, Charlie]
    Bob:     [Alice, Charlie]
    Charlie: [Alice, Bob, Diana]
    Diana:   [Charlie]
    ```

    ✅ Fast to find neighbors (\(\mathcal{O}(1)\) per neighbor)
    ✅ Space-efficient for sparse graphs
    ✅ Most commonly used in practice

    ### 3. Adjacency Matrix
    An \(n 	imes n\) matrix where entry \(A_{ij} = 1\) if there's an edge from \(i\) to \(j\).

    ```
        Alice Bob Charlie Diana
    Alice  0    1     1      0
    Bob    1    0     1      0
    Charlie 1   1     0      1
    Diana  0    0     1      0
    ```

    ✅ Fast to check if any two nodes are connected (\(\mathcal{O}(1)\))
    ❌ Uses \(\mathcal{O}(n^2)\) memory — impractical for large graphs
    """)
    return


@app.cell
def _(mo, nx):
    G = nx.karate_club_graph()

    adj_matrix = nx.to_numpy_array(G)
    adj_list = {n: list(G.neighbors(n)) for n in G.nodes()}
    edge_list = list(G.edges())

    mo.md(
        f"""
        ## Let's Compare: Zachary's Karate Club

        We'll use a famous real-world graph: **Zachary's Karate Club**. It represents friendships between 34 members of a university karate club.

        | Metric | Value |
        |--------|-------|
        | Nodes | {G.number_of_nodes()} |
        | Edges | {G.number_of_edges()} |
        | Adj. Matrix Size | {adj_matrix.shape[0]} × {adj_matrix.shape[1]} = {adj_matrix.shape[0] * adj_matrix.shape[1]} entries |
        | Non-zero entries | {int(adj_matrix.sum())} (only {int(adj_matrix.sum()) / (adj_matrix.shape[0] * adj_matrix.shape[1]) * 100:.1f}% filled) |

        Notice how **sparse** the adjacency matrix is! That's why adjacency lists are usually preferred.
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
    ## Interactive: Building Graphs Programmatically

    Let's explore different graph models and see how they look:
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
def _(mo):
    mo.md("""
    ## Understanding Graph Models

    Each model captures different properties of real-world networks:

    ### 🎲 Erdos-Renyi (Random)
    Every pair of nodes has probability \(p\) of being connected.
    - **Degree distribution**: Poisson (bell-shaped) — most nodes have similar degree
    - **Realism**: Low — real networks aren't this random

    ### 🌟 Barabasi-Albert (Preferential Attachment)
    New nodes are more likely to connect to already well-connected nodes ("the rich get richer").
    - **Degree distribution**: Power law — few hubs, many low-degree nodes
    - **Realism**: High — the internet, social networks, and citation networks follow this pattern

    ### 🔗 Watts-Strogatz (Small World)
    Start with a regular ring lattice, then randomly rewire some edges.
    - **Key property**: High clustering (my friends know each other) + short paths (six degrees of separation)
    - **Realism**: High — social networks exhibit this "small world" phenomenon
    """)
    return


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
    for k, v in props.items():
        ax_p.text(0.1, y, f"{k}: {v}", fontsize=13, transform=ax_p.transAxes)
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
    ## Advanced Visualization: Graph Layouts

    How we position nodes visually matters a lot. Different layout algorithms reveal different structures:
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

    fig_layout, axes_layout = plt.subplots(2, 2, figsize=(14, 12))
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

    ✅ Graphs can be stored as edge lists, adjacency lists, or adjacency matrices
    ✅ The adjacency matrix is simple but wasteful for sparse graphs
    ✅ Real-world graphs are almost always sparse
    ✅ Different random graph models capture different real-world properties
    ✅ Layout algorithms reveal different structural perspectives

    **Next up:** How do we traverse graphs? BFS, DFS, and finding paths!
    """)
    return


if __name__ == "__main__":
    app.run()
