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

    return mo, np, nx, plt


@app.cell
def _(mo):
    mo.md("""
    # Graph Foundations: What Is a Graph?

    Welcome to the first notebook of the Graph Workshop! Let's start from the very beginning.

    ## What is a Graph?

    A **graph** is a mathematical structure used to model relationships between objects. It consists of:

    - **Nodes** (also called **vertices**): the objects themselves
    - **Edges** (also called **links**): the relationships between objects

    > Think of a social network: people are **nodes**, friendships are **edges**.
    > In a road map: cities are **nodes**, roads connecting them are **edges**.

    Graphs are everywhere once you start looking! They model social networks, transportation systems, biological pathways, the internet, recommendation systems, and much more.
    """)
    return


@app.cell
def _(mo):
    mo.md("""
    ## Hands-On: Our First Graph

    Let's create a tiny social network and visualize it. We'll use **NetworkX** — Python's most popular graph library.
    """)
    return


@app.cell
def _(mo, nx, plt):
    G = nx.Graph()
    G.add_node("Alice")
    G.add_node("Bob")
    G.add_node("Charlie")
    G.add_node("Diana")
    G.add_edge("Alice", "Bob")
    G.add_edge("Alice", "Charlie")
    G.add_edge("Bob", "Charlie")
    G.add_edge("Charlie", "Diana")

    fig, ax = plt.subplots(figsize=(8, 5))
    pos = nx.spring_layout(G, seed=42)
    nx.draw_networkx_nodes(G, pos, node_color="lightblue", node_size=500, ax=ax)
    nx.draw_networkx_labels(G, pos, font_weight="bold", ax=ax)
    nx.draw_networkx_edges(G, pos, width=1.5, alpha=0.7, ax=ax)
    ax.set_title("A Tiny Social Network", fontsize=14)
    ax.axis("off")
    plt.tight_layout()

    mo.mpl.interactive(plt.gcf())
    return (G,)


@app.cell
def _(mo):
    mo.md("""
    ## Key Terminology

    | Term | Meaning | Example |
    |------|---------|---------|
    | **Node (Vertex)** | An entity in the graph | Alice, Bob |
    | **Edge (Link)** | A connection between two nodes | Alice—Bob |
    | **Degree** | Number of edges connected to a node | Alice knows 2 people → degree 2 |
    | **Neighbor** | A node connected by an edge | Bob is Alice's neighbor |
    | **Path** | A sequence of edges connecting nodes | Alice → Bob → Charlie |
    | **Component** | A connected subgraph | A group of people all reachable through friendships |

    Let's inspect these properties for our social network:
    """)
    return


@app.cell
def _(G, mo):
    nodes_info = {n: {"degree": G.degree(n), "neighbors": list(G.neighbors(n))} for n in G.nodes()}
    mo.ui.table([{"Node": n, "Degree": v["degree"], "Neighbors": ", ".join(v["neighbors"])} for n, v in nodes_info.items()])
    return


@app.cell
def _(mo):
    mo.md("""
    ## Types of Graphs

    Not all graphs are the same. Here are the most common types:

    ### Undirected vs Directed
    - **Undirected**: edges have no direction (like friendships)
    - **Directed (Digraph)**: edges have a direction (like Twitter follows — A follows B doesn't mean B follows A)

    ### Weighted vs Unweighted
    - **Unweighted**: all edges are equal
    - **Weighted**: edges have weights (like distance between cities, strength of a relationship)

    ### Let's see the difference:
    """)
    return


@app.cell
def _(mo, nx, plt):
    DG = nx.DiGraph()
    DG.add_edge("Alice", "Bob", weight=3)
    DG.add_edge("Bob", "Alice", weight=1)
    DG.add_edge("Alice", "Charlie", weight=2)
    DG.add_edge("Charlie", "Diana", weight=5)
    DG.add_edge("Diana", "Alice", weight=1)

    fig2, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 5))

    pos2 = nx.spring_layout(DG, seed=42)

    nx.draw_networkx_nodes(DG, pos2, node_color="lightgreen", node_size=500, ax=ax1)
    nx.draw_networkx_labels(DG, pos2, font_weight="bold", ax=ax1)
    nx.draw_networkx_edges(DG, pos2, width=1.5, alpha=0.7, ax=ax1, arrows=True, arrowsize=20)
    ax1.set_title("Directed Graph (arrows show direction)", fontsize=12)
    ax1.axis("off")

    nx.draw_networkx_nodes(DG, pos2, node_color="lightgreen", node_size=500, ax=ax2)
    nx.draw_networkx_labels(DG, pos2, font_weight="bold", ax=ax2)
    nx.draw_networkx_edges(
        DG, pos2, width=3, alpha=0.7, ax=ax2, arrows=True, arrowsize=20,
        edge_color=[DG[u][v]["weight"] for u, v in DG.edges()],
        edge_cmap=plt.cm.Blues,
    )
    edge_labels = {(u, v): DG[u][v]["weight"] for u, v in DG.edges()}
    nx.draw_networkx_edge_labels(DG, pos2, edge_labels, ax=ax2)
    ax2.set_title("Weighted Directed Graph (thicker = heavier)", fontsize=12)
    ax2.axis("off")

    plt.tight_layout()
    mo.mpl.interactive(plt.gcf())
    return


@app.cell
def _(mo):
    mo.md("""
    ## Interactive: Explore Degree Distribution

    Degree tells us how connected a node is. Let's generate random graphs and see how degrees are distributed.
    """)
    return


@app.cell
def _(mo):
    n_nodes = mo.ui.slider(5, 100, step=5, value=20, label="Number of nodes")
    edge_prob = mo.ui.slider(0.0, 1.0, step=0.05, value=0.2, label="Edge probability")

    mo.hstack([n_nodes, edge_prob], gap=2)
    return edge_prob, n_nodes


@app.cell
def _(edge_prob, mo, n_nodes, np, nx, plt):
    G_rand = nx.erdos_renyi_graph(n_nodes.value, edge_prob.value, seed=42)
    degrees = [d for _, d in G_rand.degree()]

    fig3, (ax_hist, ax_net) = plt.subplots(1, 2, figsize=(14, 5))

    ax_hist.hist(degrees, bins=min(20, n_nodes.value), color="steelblue", edgecolor="white", alpha=0.7)
    ax_hist.set_xlabel("Degree")
    ax_hist.set_ylabel("Frequency")
    ax_hist.set_title(f"Degree Distribution (avg degree = {np.mean(degrees):.1f})")

    pos_rand = nx.spring_layout(G_rand, seed=42)
    nx.draw_networkx_nodes(G_rand, pos_rand, node_color="lightblue", node_size=100, ax=ax_net, alpha=0.8)
    nx.draw_networkx_edges(G_rand, pos_rand, width=0.5, alpha=0.3, ax=ax_net)
    ax_net.set_title(f"Random Graph ({n_nodes.value} nodes, p={edge_prob.value})")
    ax_net.axis("off")

    plt.tight_layout()
    mo.mpl.interactive(plt.gcf())
    return (G_rand,)


@app.cell
def _(mo):
    mo.md("""
    ## The Handshaking Lemma

    One of the most fundamental theorems in graph theory:

    > **The sum of all node degrees equals twice the number of edges.**

    $$\sum_{v \in V} \deg(v) = 2|E|$$

    Why? Because each edge contributes to the degree of **two** nodes.

    Let's verify this on our graphs.
    """)
    return


@app.cell
def _(G, G_rand):
    def verify_handshaking(graph, name):
        n_edges = graph.number_of_edges()
        sum_degrees = sum(d for _, d in graph.degree())
        twice_edges = 2 * n_edges
        return {
            "Graph": name,
            "Sum of Degrees": sum_degrees,
            "2 × Edges": twice_edges,
            "Match ✓": sum_degrees == twice_edges,
        }

    results = [verify_handshaking(G, "Social Network"), verify_handshaking(G_rand, "Random Graph")]
    return (results,)


@app.cell
def _(mo, results):
    mo.ui.table(results)
    return


@app.cell
def _(mo):
    mo.md("""
    ## Summary

    Congratulations! You've learned the foundations of graph theory:

    ✅ What a graph is (nodes + edges)
    ✅ Key terminology (degree, neighbors, paths, components)
    ✅ Types of graphs (directed/undirected, weighted/unweighted)
    ✅ How to create and visualize graphs with NetworkX
    ✅ The Handshaking Lemma

    **Next up:** We'll dive deeper into how graphs are represented in code and how to build more complex networks.
    """)
    return


if __name__ == "__main__":
    app.run()
