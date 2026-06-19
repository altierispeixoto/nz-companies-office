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
    from collections import deque
    from queue import PriorityQueue

    return mo, nx, plt


@app.cell
def _(mo):
    mo.md("""
    # Graph Traversal & Path Finding

    Once we have a graph, the most fundamental operation is **traversal** — visiting nodes in a systematic way.

    This notebook covers:
    - **BFS** (Breadth-First Search): Explore level by level
    - **DFS** (Depth-First Search): Explore branch by branch
    - **Shortest Paths**: Finding the most efficient route
    - **Connected Components**: Finding islands in the graph
    """)
    return


@app.cell
def _(mo):
    mo.md("""
    ## Breadth-First Search (BFS)

    **BFS** explores a graph level by level. It starts at a source node, visits all its neighbors first, then the neighbors' neighbors, and so on.

    > 🧠 **Analogy**: An epidemic spreading — everyone who's infected spreads to their direct contacts simultaneously.

    **Key property**: BFS finds the **shortest path** in an **unweighted** graph.
    """)
    return


@app.cell
def _(mo, nx, plt):
    G_bfs = nx.karate_club_graph()
    source = 0

    bfs_edges = list(nx.bfs_edges(G_bfs, source))
    bfs_nodes = [source] + [v for _, v in bfs_edges]
    bfs_levels = {}
    for u, v in bfs_edges:
        if u not in bfs_levels:
            bfs_levels[v] = 1
        else:
            bfs_levels[v] = bfs_levels[u] + 1
    bfs_levels[source] = 0

    fig_bfs, ax_bfs = plt.subplots(figsize=(10, 7))
    pos_bfs = nx.spring_layout(G_bfs, seed=42)

    nx.draw_networkx_edges(G_bfs, pos_bfs, alpha=0.15, ax=ax_bfs)
    nx.draw_networkx_edges(G_bfs, pos_bfs, edgelist=bfs_edges, width=2.5, edge_color="orange", alpha=0.8, ax=ax_bfs)

    colors = ["#ff6b6b" if n == source else "#ffd43b" for n in G_bfs.nodes()]
    sizes = [300 if n == source else 200 for n in G_bfs.nodes()]
    nx.draw_networkx_nodes(G_bfs, pos_bfs, node_color=colors, node_size=sizes, ax=ax_bfs)
    nx.draw_networkx_labels(G_bfs, pos_bfs, font_size=9, ax=ax_bfs)

    ax_bfs.set_title(f"BFS Tree from Node {source} (orange edges show traversal order)", fontsize=13)
    ax_bfs.axis("off")
    plt.tight_layout()
    mo.mpl.interactive(plt.gcf())
    return G_bfs, bfs_levels, source


@app.cell
def _(bfs_levels, mo):
    mo.md(
        f"""
        **BFS Levels from Node 0:**
        """
    )
    mo.ui.table([{"Node": str(k), "BFS Level (distance)": v} for k, v in sorted(bfs_levels.items(), key=lambda x: x[1])])
    return


@app.cell
def _(mo):
    mo.md("""
    ## Depth-First Search (DFS)

    **DFS** explores a graph by going as deep as possible along each branch before backtracking.

    > 🧠 **Analogy**: Exploring a maze — you follow a path until you hit a dead end, then backtrack.

    **Key property**: DFS is great for topological sorting, detecting cycles, and solving mazes.
    """)
    return


@app.cell
def _(G_bfs, mo, nx, plt, source):
    dfs_edges = list(nx.dfs_edges(G_bfs, source))
    dfs_order = [source] + [v for _, v in dfs_edges]

    fig_dfs, ax_dfs = plt.subplots(figsize=(10, 7))
    pos_dfs = nx.spring_layout(G_bfs, seed=42)

    nx.draw_networkx_edges(G_bfs, pos_dfs, alpha=0.15, ax=ax_dfs)
    nx.draw_networkx_edges(G_bfs, pos_dfs, edgelist=dfs_edges, width=2.5, edge_color="purple", alpha=0.8, ax=ax_dfs)

    colors_dfs = ["#ff6b6b" if n == source else "#b197fc" for n in G_bfs.nodes()]
    nx.draw_networkx_nodes(G_bfs, pos_dfs, node_color=colors_dfs, node_size=200, ax=ax_dfs)
    nx.draw_networkx_labels(G_bfs, pos_dfs, font_size=9, ax=ax_dfs)

    ax_dfs.set_title(f"DFS Tree from Node {source} (purple edges show traversal order)", fontsize=13)
    ax_dfs.axis("off")
    plt.tight_layout()
    mo.mpl.interactive(plt.gcf())
    return


@app.cell
def _(mo):
    mo.md("""
    ## BFS vs DFS — When to Use What?

    | Criteria | BFS | DFS |
    |----------|-----|-----|
    | **Shortest path** (unweighted) | ✅ Guaranteed | ❌ Not guaranteed |
    | **Memory** | \(\mathcal{O}(w)\) — width can be large | \(\mathcal{O}(d)\) — depth usually smaller |
    | **Cycle detection** | Can detect | ✅ Excellent |
    | **Topological sort** | ❌ | ✅ |
    | **Connected components** | ✅ | ✅ |

    Both have \(\mathcal{O}(V + E)\) time complexity — they visit every node and edge once.
    """)
    return


@app.cell
def _(mo):
    mo.md("""
    ## Interactive: BFS vs DFS on Random Graphs

    Watch how BFS and DFS explore differently:
    """)
    return


@app.cell
def _(mo):
    n_slider = mo.ui.slider(10, 60, step=5, value=30, label="Number of nodes")
    start_node = mo.ui.slider(0, 9, step=1, value=0, label="Starting node (0-indexed)")
    mo.hstack([n_slider, start_node], gap=2)
    return n_slider, start_node


@app.cell
def _(mo, n_slider, nx, plt, start_node):
    G_ex = nx.erdos_renyi_graph(n_slider.value, 0.12, seed=42)

    if start_node.value >= G_ex.number_of_nodes():
        src = 0
    else:
        src = start_node.value

    bfs_edges_ex = list(nx.bfs_edges(G_ex, src))
    dfs_edges_ex = list(nx.dfs_edges(G_ex, src))

    fig_ex, (ax_b, ax_d) = plt.subplots(1, 2, figsize=(16, 6))
    pos_ex = nx.spring_layout(G_ex, seed=42)

    nx.draw_networkx_edges(G_ex, pos_ex, alpha=0.1, ax=ax_b)
    nx.draw_networkx_edges(G_ex, pos_ex, edgelist=bfs_edges_ex, width=2, edge_color="orange", alpha=0.8, ax=ax_b)
    nx.draw_networkx_nodes(G_ex, pos_ex, node_color="lightblue", node_size=100, ax=ax_b)
    nx.draw_networkx_nodes(G_ex, pos_ex, nodelist=[src], node_color="red", node_size=150, ax=ax_b)
    ax_b.set_title(f"BFS — explores {len(bfs_edges_ex) + 1}/{G_ex.number_of_nodes()} nodes", fontsize=12)
    ax_b.axis("off")

    nx.draw_networkx_edges(G_ex, pos_ex, alpha=0.1, ax=ax_d)
    nx.draw_networkx_edges(G_ex, pos_ex, edgelist=dfs_edges_ex, width=2, edge_color="purple", alpha=0.8, ax=ax_d)
    nx.draw_networkx_nodes(G_ex, pos_ex, node_color="lightblue", node_size=100, ax=ax_d)
    nx.draw_networkx_nodes(G_ex, pos_ex, nodelist=[src], node_color="red", node_size=150, ax=ax_d)
    ax_d.set_title(f"DFS — explores {len(dfs_edges_ex) + 1}/{G_ex.number_of_nodes()} nodes", fontsize=12)
    ax_d.axis("off")

    plt.tight_layout()
    mo.mpl.interactive(plt.gcf())
    return


@app.cell
def _(mo):
    mo.md("""
    ## Shortest Paths

    Finding the shortest path between two nodes is one of the most practical graph problems.
    """)
    return


@app.cell
def _(G_bfs, mo, n, nx, plt):
    source_sp = 0
    target_sp = 33

    path = nx.shortest_path(G_bfs, source=source_sp, target=target_sp)
    path_length = nx.shortest_path_length(G_bfs, source=source_sp, target=target_sp)

    fig_sp, ax_sp = plt.subplots(figsize=(10, 7))
    pos_sp = nx.spring_layout(G_bfs, seed=42)

    nx.draw_networkx_edges(G_bfs, pos_sp, alpha=0.15, ax=ax_sp)

    path_edges = list(zip(path[:-1], path[1:]))
    nx.draw_networkx_edges(G_bfs, pos_sp, edgelist=path_edges, width=3, edge_color="#2b8a3e", alpha=0.9, ax=ax_sp)

    node_colors_sp = []
    for _gn in G_bfs.nodes():
        if n == source_sp:
            node_colors_sp.append("#ff6b6b")
        elif n == target_sp:
            node_colors_sp.append("#2b8a3e")
        elif n in path:
            node_colors_sp.append("#69db7c")
        else:
            node_colors_sp.append("lightblue")

    nx.draw_networkx_nodes(G_bfs, pos_sp, node_color=node_colors_sp, node_size=200, ax=ax_sp)
    nx.draw_networkx_labels(G_bfs, pos_sp, font_size=9, ax=ax_sp)

    ax_sp.set_title(f"Shortest Path: Node {source_sp} → Node {target_sp} (Length = {path_length})", fontsize=13)
    ax_sp.axis("off")
    plt.tight_layout()
    mo.mpl.interactive(plt.gcf())
    return (path,)


@app.cell
def _(mo, path):
    mo.md(f"""
    **Path**: {" → ".join(str(n) for n in path)}

    This is the shortest route through the karate club network from node 0 to node 33.
    """)
    return


@app.cell
def _(mo):
    mo.md("""
    ## Weighted Shortest Paths (Dijkstra's Algorithm)

    When edges have weights (e.g., distance, cost, time), we use **Dijkstra's algorithm** to find the path with minimum total weight.
    """)
    return


@app.cell
def _(mo, nx, plt):
    G_weighted = nx.Graph()
    cities = ["Auckland", "Hamilton", "Tauranga", "Rotorua", "Taupo", "Wellington"]
    routes = [
        ("Auckland", "Hamilton", 130),
        ("Auckland", "Tauranga", 200),
        ("Hamilton", "Tauranga", 110),
        ("Hamilton", "Rotorua", 160),
        ("Tauranga", "Rotorua", 85),
        ("Rotorua", "Taupo", 80),
        ("Taupo", "Wellington", 370),
        ("Hamilton", "Taupo", 200),
    ]

    for city in cities:
        G_weighted.add_node(city)
    for u, v, w in routes:
        G_weighted.add_edge(u, v, weight=w)

    source_city = "Auckland"
    target_city = "Wellington"

    shortest_path = nx.shortest_path(G_weighted, source=source_city, target=target_city, weight="weight")
    shortest_dist = nx.shortest_path_length(G_weighted, source=source_city, target=target_city, weight="weight")

    fig_dijk, ax_dijk = plt.subplots(figsize=(12, 7))
    pos_dijk = nx.spring_layout(G_weighted, seed=42)

    nx.draw_networkx_nodes(G_weighted, pos_dijk, node_color="lightblue", node_size=800, ax=ax_dijk)
    nx.draw_networkx_labels(G_weighted, pos_dijk, font_weight="bold", ax=ax_dijk)

    sp_edges = list(zip(shortest_path[:-1], shortest_path[1:]))
    regular_edges = [(u, v) for u, v in G_weighted.edges() if (u, v) not in sp_edges and (v, u) not in sp_edges]
    nx.draw_networkx_edges(G_weighted, pos_dijk, edgelist=regular_edges, width=1.5, alpha=0.5, ax=ax_dijk)
    nx.draw_networkx_edges(G_weighted, pos_dijk, edgelist=sp_edges, width=4, edge_color="green", alpha=0.8, ax=ax_dijk)

    edge_labels = nx.get_edge_attributes(G_weighted, "weight")
    nx.draw_networkx_edge_labels(G_weighted, pos_dijk, edge_labels=edge_labels, ax=ax_dijk, font_size=10)

    ax_dijk.set_title(f"Shortest Route: {shortest_path} (Total: {shortest_dist} km)", fontsize=13)
    ax_dijk.axis("off")
    plt.tight_layout()
    mo.mpl.interactive(plt.gcf())
    return shortest_dist, shortest_path


@app.cell
def _(mo, shortest_dist, shortest_path):
    mo.md(f"""
    **Shortest route**: {" → ".join(shortest_path)}  
    **Total distance**: {shortest_dist} km

    Dijkstra's algorithm efficiently finds this by always expanding the node with the smallest known distance.
    """)
    return


@app.cell
def _(mo):
    mo.md("""
    ## Connected Components

    A **connected component** is a set of nodes where every node can reach every other node. If the graph is disconnected, it breaks into multiple components.
    """)
    return


@app.cell
def _(G_bfs, mo, nx, plt):
    components = list(nx.connected_components(G_bfs))
    n_components = len(components)
    comp_sizes = [len(c) for c in components]

    G_disconnected = nx.Graph()
    G_disconnected.add_edges_from([(0, 1), (1, 2), (2, 0), (3, 4), (4, 5), (5, 3), (6,), (7, 8)])

    fig_comp, (ax_comp1, ax_comp2) = plt.subplots(1, 2, figsize=(16, 6))

    comp_colors = ["#ff6b6b", "#339af0", "#51cf66", "#cc5de8", "#f59f00"]
    for i, comp in enumerate(components):
        nx.draw_networkx_nodes(G_bfs, nx.spring_layout(G_bfs, seed=42), nodelist=list(comp),
                               node_color=comp_colors[i % len(comp_colors)],
                               node_size=150, ax=ax_comp1, label=f"Component {i+1} ({len(comp)} nodes)")
    nx.draw_networkx_edges(G_bfs, nx.spring_layout(G_bfs, seed=42), alpha=0.3, ax=ax_comp1)
    ax_comp1.set_title(f"Karate Club: {n_components} connected component{'s' if 's' else ''}", fontsize=13)
    ax_comp1.axis("off")
    ax_comp1.legend(fontsize=9)

    pos_disc = nx.spring_layout(G_disconnected, seed=42)
    for i, comp in enumerate(nx.connected_components(G_disconnected)):
        nx.draw_networkx_nodes(G_disconnected, pos_disc, nodelist=list(comp),
                               node_color=comp_colors[i % len(comp_colors)],
                               node_size=500, ax=ax_comp2, label=f"Component {i+1} ({len(comp)} nodes)")
    nx.draw_networkx_edges(G_disconnected, pos_disc, alpha=0.5, ax=ax_comp2, width=2)
    nx.draw_networkx_labels(G_disconnected, pos_disc, font_size=10, ax=ax_comp2)
    ax_comp2.set_title(f"Disconnected Graph: {len(list(nx.connected_components(G_disconnected)))} components", fontsize=13)
    ax_comp2.axis("off")
    ax_comp2.legend(fontsize=9)

    plt.tight_layout()
    mo.mpl.interactive(plt.gcf())
    return


@app.cell
def _(mo):
    mo.md("""
    ## Interactive: Path Finder

    Find the shortest path between any two nodes in a graph:
    """)
    return


@app.cell
def _(mo, nx):
    G_path = nx.karate_club_graph()
    node_a = mo.ui.slider(0, G_path.number_of_nodes() - 1, step=1, value=0, label="From node")
    node_b = mo.ui.slider(0, G_path.number_of_nodes() - 1, step=1, value=33, label="To node")
    mo.hstack([node_a, node_b], gap=2)
    return G_path, node_a, node_b


@app.cell
def _(G_path, mo, node_a, node_b, nx, plt):
    na = node_a.value
    nb = node_b.value

    if nx.has_path(G_path, na, nb):
        p = nx.shortest_path(G_path, na, nb)
        pl = len(p) - 1
        fig_path, ax_path = plt.subplots(figsize=(10, 7))
        pos_path = nx.spring_layout(G_path, seed=42)

        nx.draw_networkx_edges(G_path, pos_path, alpha=0.15, ax=ax_path)

        p_edges = list(zip(p[:-1], p[1:]))
        nx.draw_networkx_edges(G_path, pos_path, edgelist=p_edges, width=3, edge_color="#e03131", alpha=0.9, ax=ax_path)

        colors_path = []
        for _gn in G_path.nodes():
            if _gn == na:
                colors_path.append("#ff6b6b")
            elif _gn == nb:
                colors_path.append("#2b8a3e")
            elif _gn in p:
                colors_path.append("#ffc078")
            else:
                colors_path.append("lightblue")

        nx.draw_networkx_nodes(G_path, pos_path, node_color=colors_path, node_size=200, ax=ax_path)
        nx.draw_networkx_labels(G_path, pos_path, font_size=9, ax=ax_path)

        ax_path.set_title(f"Path {na} → {nb}: {p} (length: {pl})", fontsize=13)
        ax_path.axis("off")
        plt.tight_layout()
        mo.mpl.interactive(plt.gcf())
    else:
        mo.md(f"❌ No path exists between node {na} and node {nb}")
    return


@app.cell
def _(mo):
    mo.md("""
    ## Summary

    ✅ **BFS**: Level-by-level exploration, finds shortest paths in unweighted graphs
    ✅ **DFS**: Deep exploration, good for cycle detection and topological sorting
    ✅ **Dijkstra's algorithm**: Shortest paths in weighted graphs (road networks, etc.)
    ✅ **Connected components**: Find islands within the graph
    ✅ All these algorithms run in \(\mathcal{O}(V + E)\) time

    **Next up:** How do we measure importance in a network? We'll explore centrality metrics!
    """)
    return


@app.cell
def _():
    return


if __name__ == "__main__":
    app.run()
