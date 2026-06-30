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
    # 01 — Graph Foundations: What Is a Graph?

    Welcome! This notebook builds your intuition for what graphs are and why they matter.

    | # | Topic | What You'll Learn |
    |---|-------|-------------------|
    | 1 | **What Is a Graph?** | Nodes, edges, and the core idea |
    | 2 | **Our First Graph** | Build and visualize a tiny social network |
    | 3 | **Key Terminology** | Degree, neighbors, paths, components |
    | 4 | **Types of Graphs** | Directed/undirected, weighted/unweighted |
    | 5 | **Interactive Degree Distribution** | Explore random graphs with sliders |
    | 6 | **The Handshaking Lemma** | A fundamental graph theorem |

    ---

    A **graph** is a structure for modeling **relationships between objects**:

    - **Nodes (vertices)** — the objects
    - **Edges (links)** — the relationships

    > **Analogy**: People at a party are **nodes**. If two people have met, there's an **edge** between them. The whole party is a **graph**.
    """)
    return


@app.cell
def _(mo):
    mo.md("""
    "\"
    ## Topic 1: What Is a Graph?

    A graph answers one question: **what connects to what?**

    | Real-world system | Nodes | Edges |
    |---|---|--|
    | Social network | People | Friendships |
    | Road map | Cities | Roads |
    | The internet | Websites | Hyperlinks |
    | Brain | Neurons | Synapses |
    | Protein network | Proteins | Interactions |

    > **The power of graphs**: Once you encode a system as a graph, you can ask universal questions — Who is most connected? What's the shortest path? Are there clusters?


    "\""
        "Let's build our first graph and make this concrete."
        "
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
    ## Topic 2: Key Terminology

    Once we have a graph, we need a shared vocabulary to talk about it.

    | Term | Definition | In our social network |
    |------|-----------|---------------------|
    | **Node** | An entity | Alice, Bob, Charlie, Diana |
    | **Edge** | A connection between two nodes | Alice—Bob |
    | **Degree** | Number of edges incident to a node | Alice has degree 2 (Bob, Charlie) |
    | **Neighbor** | A node reached by one edge | Bob and Charlie are Alice's neighbors |
    | **Path** | A sequence of edges connecting two nodes | Alice → Bob → Charlie |
    | **Component** | A maximal connected subgraph | All 4 people are one component |

    > **How it works**: The degree of a node counts its connections. A path is any route you can walk along edges. A component is everything reachable from a starting node.
    """)
    return


@app.cell
def _(G, mo):
    nodes_info = {n: {"degree": G.degree(n), "neighbors": list(G.neighbors(n))} for n in G.nodes()}
    mo.ui.table(
        [{"Node": n, "Degree": v["degree"], "Neighbors": ", ".join(v["neighbors"])} for n, v in nodes_info.items()]
    )
    return


@app.cell
def _(mo):
    mo.md("""
    ## Topic 3: Types of Graphs

    Not all graphs are the same. The type you choose depends on what you're modeling.

    ### Undirected vs Directed

    | | Undirected | Directed (Digraph) |
    |---|---|---|
    | **Edges** | No direction (friendship) | Direction matters (Twitter follow) |
    | **Notation** | `(u, v)` means same as `(v, u)` | `(u, v)` means u→v |
    | **Analogy** | Handshake (mutual) | Gift (one-way) |

    ### Weighted vs Unweighted

    | | Unweighted | Weighted |
    |---|---|---|
    | **Edges** | All equal | Have a numeric value |
    | **Analogy** | "Knows" | "Knows well" (strength: 1–5) |
    | **Example** | Friendship graph | Road distances |

    > **When to use each**: Use **undirected** for symmetric relationships (siblings, co-authors). Use **direct`ed** for asymmetric ones (followers, citations). Add **weights** when connections have different strengths (distances, ratings, capacities).
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
        DG,
        pos2,
        width=3,
        alpha=0.7,
        ax=ax2,
        arrows=True,
        arrowsize=20,
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
    ## Topic 4: Interactive Degree Distribution

    Degree tells us **how connected a node is**. In a random graph, most nodes have similar degree (bell curve). In real networks, a few nodes have very high degree (power law).

    > **Analogy**: In a conference, most people know 5–20 people (bell curve). On Twitter, a few celebrities have millions of followers while most have dozens (power law).

    Use the sliders below to generate random graphs and see how the degree distribution changes with graph size and edge density.
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
    ## Topic 5: The Handshaking Lemma

    One of the most fundamental theorems in graph theory:

    > **The sum of all node degrees equals twice the number of edges.**

    $$\sum_{v \in V} \deg(v) = 2|E|$$

    **Why?** Each edge contributes 1 to the degree of **both** of its endpoints — so every edge adds 2 to the total degree sum.

    > **Analogy**: At a party, if you count everyone's handshakes and add them up, you get twice the actual number of handshakes (because each handshake involves two people).

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

    | # | You've Learned | Key Insight |
    |---|---------------|-------------|
    | 1 | **What a graph is** | Nodes + edges model any system of relationships |
    | 2 | **Our first graph** | NetworkX makes creating graphs trivial |
    | 3 | **Key terminology** | Degree, neighbors, paths, components |
    | 4 | **Types of graphs** | Directed/undirected, weighted/unweighted |
    | 5 | **Degree distribution** | Real networks have "rich-get-richer" dynamics |
    | 6 | **Handshaking lemma** | Sum of degrees = 2 × edges (always!) |

    **Next up:** [02 — Graph Representation](./02_graph_representation.py) — how graphs are stored in a computer and how to build complex networks.
    """)
    return


if __name__ == "__main__":
    app.run()
