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

    return mo, nx, plt


@app.cell
def _(mo):
    mo.md("""
    # Graph Traversal & Path Finding

    Once we **represent** a graph (edge lists, adjacency lists, matrices), the next step is **traversing** it — visiting nodes in a systematic way. This is the foundation of almost every graph algorithm.

    ## What You'll Learn

    | Topic | What It Means | Real-World Use |
    |-------|--------------|----------------|
    | **BFS** | Explore level by level | Social network friend suggestions, web crawling |
    | **DFS** | Explore branch by branch | Maze solving, dependency resolution |
    | **Shortest Paths** | Find the most efficient route | GPS navigation, network routing |
    | **Connected Components** | Find subgraphs that are isolated | Fraud detection, image segmentation |

    All these algorithms run in **O(V + E)** time — each node and edge is visited at most once.
    """)
    return


@app.cell
def _(mo):
    mo.md("""
    ## Topic 1: Breadth-First Search (BFS)

    ### How It Works

    BFS explores a graph **level by level**. Start at a source node, visit every direct neighbor first (level 1), then their neighbors (level 2), and so on.

    **Analogy**: An epidemic spreading. Everyone infected spreads to their direct contacts simultaneously. After 1 round, everyone 1 handshake away is infected. After 2 rounds, everyone 2 handshakes away.

    **Step-by-step algorithm**:

    1. Start at a source node, mark it as **visited** and add it to a **queue**
    2. While the queue is not empty:
       a. **Dequeue** a node
       b. For each **unvisited neighbor**, mark it visited and **enqueue** it
    3. The order nodes are dequeued is the BFS traversal order

    ```
    BFS(graph, start):
        visited = {start}
        queue = [start]
        while queue is not empty:
            node = queue.pop_front()
            for neighbor in graph.neighbors(node):
                if neighbor not in visited:
                    visited.add(neighbor)
                    queue.append(neighbor)
    ```

    **Key property**: BFS finds the **shortest path** in an **unweighted** graph. The first time we reach a node, it's via the shortest route.

    Let's see it in action on Zachary's Karate Club graph:
    """)
    return


@app.cell
def _(mo, nx, plt):
    G_bfs = nx.karate_club_graph()
    source = 0

    bfs_edges = list(nx.bfs_edges(G_bfs, source))
    bfs_levels = {}
    for u, v in bfs_edges:
        if u not in bfs_levels:
            bfs_levels[v] = 1
        else:
            bfs_levels[v] = bfs_levels[u] + 1
    bfs_levels[source] = 0

    _fig_bfs, ax_bfs = plt.subplots(figsize=(10, 7))
    pos_bfs = nx.spring_layout(G_bfs, seed=42)

    nx.draw_networkx_edges(G_bfs, pos_bfs, alpha=0.15, ax=ax_bfs)
    nx.draw_networkx_edges(G_bfs, pos_bfs, edgelist=bfs_edges, width=2.5, edge_color="orange", alpha=0.8, ax=ax_bfs)

    colors = ["#ff6b6b" if n == source else "#ffd43b" for n in G_bfs.nodes()]
    sizes = [300 if n == source else 200 for n in G_bfs.nodes()]
    nx.draw_networkx_nodes(G_bfs, pos_bfs, node_color=colors, node_size=sizes, ax=ax_bfs)
    nx.draw_networkx_labels(G_bfs, pos_bfs, font_size=9, ax=ax_bfs)

    ax_bfs.set_title(f"BFS Tree from Node {source} — orange edges show traversal order, red is start", fontsize=13)
    ax_bfs.axis("off")
    plt.tight_layout()
    mo.mpl.interactive(plt.gcf())
    return G_bfs, bfs_levels, source


@app.cell
def _(bfs_levels, mo):
    mo.md(
        """
        **BFS Levels from Node 0:**

        The table below shows how BFS assigns each node a **level** — the shortest-path distance from the source.

        - Level 0: The source node itself
        - Level 1: Direct friends of node 0
        - Level 2: Friends of friends
        - And so on...
        """
    )
    mo.ui.table(
        [
            {"Node": str(k), "BFS Level (shortest distance)": v}
            for k, v in sorted(bfs_levels.items(), key=lambda x: x[1])
        ]
    )
    return


@app.cell
def _(mo):
    mo.md("""
    ## Topic 2: Depth-First Search (DFS)

    ### How It Works

    DFS explores a graph by going **as deep as possible** along each branch before **backtracking**. Instead of a queue (BFS), DFS uses a **stack** (or recursion).

    **Analogy**: Exploring a maze. You follow a path until you hit a dead end, then backtrack to the last junction and try the next path. You go deep first, wide second.

    **Step-by-step algorithm (iterative, using a stack)**:

    1. Start at a source node, push it onto a **stack**
    2. While the stack is not empty:
       a. **Pop** a node from the stack
       b. If it hasn't been visited, mark it visited and **push all its unvisited neighbors** onto the stack
    3. The order nodes are popped is the DFS traversal order

    ```
    DFS(graph, start):
        visited = {}
        stack = [start]
        while stack is not empty:
            node = stack.pop()
            if node not in visited:
                visited.add(node)
                for neighbor in graph.neighbors(node):
                    if neighbor not in visited:
                        stack.append(neighbor)
    ```

    **Key properties**:
    - Uses **less memory** than BFS on wide graphs (tracks a path, not a frontier)
    - Great for **cycle detection**, **topological sorting**, and **maze solving**
    - Does **NOT** guarantee shortest paths

    Let's compare with BFS on the same graph:
    """)
    return


@app.cell
def _(G_bfs, mo, nx, plt, source):
    dfs_edges = list(nx.dfs_edges(G_bfs, source))

    _fig_dfs, ax_dfs = plt.subplots(figsize=(10, 7))
    pos_dfs = nx.spring_layout(G_bfs, seed=42)

    nx.draw_networkx_edges(G_bfs, pos_dfs, alpha=0.15, ax=ax_dfs)
    nx.draw_networkx_edges(G_bfs, pos_dfs, edgelist=dfs_edges, width=2.5, edge_color="purple", alpha=0.8, ax=ax_dfs)

    colors_dfs = ["#ff6b6b" if n == source else "#b197fc" for n in G_bfs.nodes()]
    nx.draw_networkx_nodes(G_bfs, pos_dfs, node_color=colors_dfs, node_size=200, ax=ax_dfs)
    nx.draw_networkx_labels(G_bfs, pos_dfs, font_size=9, ax=ax_dfs)

    ax_dfs.set_title(f"DFS Tree from Node {source} — purple edges show traversal path", fontsize=13)
    ax_dfs.axis("off")
    plt.tight_layout()
    mo.mpl.interactive(plt.gcf())
    return


@app.cell
def _(mo):
    mo.md("""
    ## Topic 3: BFS vs DFS — When to Use What?

    Both algorithms visit every node and edge exactly once (O(V + E) time), but their **exploration order** makes each suitable for different problems.

    | Criteria | BFS | DFS |
    |----------|-----|-----|
    | **Shortest path** (unweighted) | ✅ Guaranteed — first discovery = shortest route | ❌ Not guaranteed — may find a longer path first |
    | **Memory** | O(w) — queue grows with **width** of the graph | O(d) — stack grows with **depth** of the graph |
    | **Cycle detection** | Can detect | ✅ Excellent — natural fit |
    | **Topological sort** | ❌ | ✅ Works perfectly |
    | **Connected components** | ✅ | ✅ |
    | **Web crawling** | ✅ Natural — explore broadly first | ❌ Could go infinitely deep on one site |

    **Rule of thumb**:
    - Use **BFS** when: The target is close to the start, or you need the shortest path
    - Use **DFS** when: Memory is limited, or you need to explore the entire graph

    ### Interactive: Watch BFS vs DFS in Action

    Run a random graph and see how each algorithm explores differently:
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
    src = 0 if start_node.value >= G_ex.number_of_nodes() else start_node.value

    bfs_edges_ex = list(nx.bfs_edges(G_ex, src))
    dfs_edges_ex = list(nx.dfs_edges(G_ex, src))

    _fig_ex, (ax_b, ax_d) = plt.subplots(1, 2, figsize=(16, 6))
    pos_ex = nx.spring_layout(G_ex, seed=42)

    nx.draw_networkx_edges(G_ex, pos_ex, alpha=0.1, ax=ax_b)
    nx.draw_networkx_edges(G_ex, pos_ex, edgelist=bfs_edges_ex, width=2, edge_color="orange", alpha=0.8, ax=ax_b)
    nx.draw_networkx_nodes(G_ex, pos_ex, node_color="lightblue", node_size=100, ax=ax_b)
    nx.draw_networkx_nodes(G_ex, pos_ex, nodelist=[src], node_color="red", node_size=150, ax=ax_b)
    ax_b.set_title(
        f"BFS — explores {len(bfs_edges_ex) + 1}/{G_ex.number_of_nodes()} nodes (level by level)", fontsize=12
    )
    ax_b.axis("off")

    nx.draw_networkx_edges(G_ex, pos_ex, alpha=0.1, ax=ax_d)
    nx.draw_networkx_edges(G_ex, pos_ex, edgelist=dfs_edges_ex, width=2, edge_color="purple", alpha=0.8, ax=ax_d)
    nx.draw_networkx_nodes(G_ex, pos_ex, node_color="lightblue", node_size=100, ax=ax_d)
    nx.draw_networkx_nodes(G_ex, pos_ex, nodelist=[src], node_color="red", node_size=150, ax=ax_d)
    ax_d.set_title(f"DFS — explores {len(dfs_edges_ex) + 1}/{G_ex.number_of_nodes()} nodes (deep first)", fontsize=12)
    ax_d.axis("off")

    plt.tight_layout()
    mo.mpl.interactive(plt.gcf())
    return


@app.cell
def _(mo):
    mo.md("""
    ## Topic 4: Shortest Paths (Unweighted Graphs)

    In an **unweighted graph**, every edge has the same "cost". BFS naturally finds the shortest path because:
    - It explores in order of distance from the source
    - The first time it discovers a node, it's via the shortest possible route

    **Use case**: Friend recommendations on social networks. "People you may know" is often BFS at distance 2: friends of friends you're not yet connected to.

    Let's find the shortest path between two specific members of the karate club:
    """)
    return


@app.cell
def _(G_bfs, mo, nx, plt):
    source_sp = 0
    target_sp = 33

    path = nx.shortest_path(G_bfs, source=source_sp, target=target_sp)
    path_length = nx.shortest_path_length(G_bfs, source=source_sp, target=target_sp)

    _fig_sp, ax_sp = plt.subplots(figsize=(10, 7))
    pos_sp = nx.spring_layout(G_bfs, seed=42)

    nx.draw_networkx_edges(G_bfs, pos_sp, alpha=0.15, ax=ax_sp)

    path_edges = list(zip(path[:-1], path[1:]))
    nx.draw_networkx_edges(G_bfs, pos_sp, edgelist=path_edges, width=3, edge_color="#2b8a3e", alpha=0.9, ax=ax_sp)

    node_colors_sp = []
    for current_node in G_bfs.nodes():
        if current_node == source_sp:
            node_colors_sp.append("#ff6b6b")
        elif current_node == target_sp:
            node_colors_sp.append("#2b8a3e")
        elif current_node in path:
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
    **Path from Node 0 → Node 33**: {" → ".join(str(n) for n in path)}

    **Length**: {len(path) - 1} edges

    This is the shortest route through the karate club network. BFS found it by expanding level by level until it reached node 33 — guaranteeing no shorter path exists.
    """)
    return


@app.cell
def _(mo):
    mo.md("""
    ## Topic 5: Weighted Shortest Paths (Dijkstra's Algorithm)

    What if edges have different **costs** (distance, time, price)?

    In a weighted graph, the shortest path isn't the one with the fewest edges — it's the one with the **lowest total weight**.

    **Dijkstra's algorithm** solves this:
    1. Start at the source, set its distance to 0
    2. Always expand the **unvisited node with the smallest known distance**
    3. Update neighbors' distances if a shorter route is found
    4. Repeat until the target is reached

    **Analogy**: You're at an airport. Instead of exploring gates one by one (BFS), you check the departure board and always go to the **closest unvisited city** next. This guarantees you find the shortest route to every city.

    Let's see it on a New Zealand road network:
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
        ("Hamilton", "Taupo", 153),
    ]

    for city_name in cities:
        G_weighted.add_node(city_name)
    for c1, c2, dist in routes:
        G_weighted.add_edge(c1, c2, weight=dist)

    source_city = "Auckland"
    target_city = "Wellington"

    shortest_path = nx.shortest_path(G_weighted, source=source_city, target=target_city, weight="weight")
    shortest_dist = nx.shortest_path_length(G_weighted, source=source_city, target=target_city, weight="weight")

    _fig_dijk, ax_dijk = plt.subplots(figsize=(12, 7))
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

    **Why not go via Tauranga?** Auckland → Tauranga (200 km) + Tauranga → Rotorua (85 km) + Rotorua → Taupo (80 km) + Taupo → Wellington (370 km) = **735 km** — much longer!

    Dijkstra's algorithm found the optimal route by always expanding the city with the smallest known distance. It correctly determined that going through Hamilton and Taupo is cheaper than taking the coastal route.

    **Limitation**: Dijkstra's algorithm doesn't work with **negative edge weights**. For those, you need Bellman-Ford.
    """)
    return


@app.cell
def _(mo):
    mo.md("""
    ## Topic 6: Connected Components

    A **connected component** is a set of nodes where every node can reach every other node. If a graph is disconnected, it splits into multiple isolated components.

    **Why this matters**:
    - **Social networks**: Find isolated communities or friend groups
    - **Fraud detection**: Identify rings of connected accounts
    - **Image segmentation**: Group pixels into objects
    - **Power grids**: Find parts of the network that could go dark if a line fails

    **How to find them**: Both BFS and DFS work. Start from any unvisited node, traverse everything reachable — that's one component. Repeat until all nodes are visited.

    Let's compare a connected graph vs a deliberately disconnected one:
    """)
    return


@app.cell
def _(G_bfs, mo, nx, plt):
    components = list(nx.connected_components(G_bfs))
    n_components = len(components)

    G_disconnected = nx.Graph()
    G_disconnected.add_edges_from([(0, 1), (1, 2), (2, 0), (3, 4), (4, 5), (5, 3), (7, 8)])
    G_disconnected.add_node(6)

    _fig_comp, (ax_comp1, ax_comp2) = plt.subplots(1, 2, figsize=(16, 6))

    comp_colors = ["#ff6b6b", "#339af0", "#51cf66", "#cc5de8", "#f59f00"]
    for i, comp in enumerate(components):
        nx.draw_networkx_nodes(
            G_bfs,
            nx.spring_layout(G_bfs, seed=42),
            nodelist=list(comp),
            node_color=comp_colors[i % len(comp_colors)],
            node_size=150,
            ax=ax_comp1,
            label=f"Component {i + 1} ({len(comp)} nodes)",
        )
    nx.draw_networkx_edges(G_bfs, nx.spring_layout(G_bfs, seed=42), alpha=0.3, ax=ax_comp1)
    ax_comp1.set_title(f"Karate Club: {n_components} connected component — the graph is intact", fontsize=13)
    ax_comp1.axis("off")
    ax_comp1.legend(fontsize=9)

    pos_disc = nx.spring_layout(G_disconnected, seed=42)
    disconnected_comps = list(nx.connected_components(G_disconnected))
    for i, comp in enumerate(disconnected_comps):
        nx.draw_networkx_nodes(
            G_disconnected,
            pos_disc,
            nodelist=list(comp),
            node_color=comp_colors[i % len(comp_colors)],
            node_size=500,
            ax=ax_comp2,
            label=f"Component {i + 1} ({len(comp)} nodes)",
        )
    nx.draw_networkx_edges(G_disconnected, pos_disc, alpha=0.5, ax=ax_comp2, width=2)
    nx.draw_networkx_labels(G_disconnected, pos_disc, font_size=10, ax=ax_comp2)
    ax_comp2.set_title(f"Disconnected Graph: {len(disconnected_comps)} components — 3 isolated groups", fontsize=13)
    ax_comp2.axis("off")
    ax_comp2.legend(fontsize=9)

    plt.tight_layout()
    mo.mpl.interactive(plt.gcf())
    return


@app.cell
def _(mo):
    mo.md("""
    ## Topic 7: Interactive Path Finder

    Now let's put it all together. Pick any two members of the karate club and see the shortest path between them in real time.

    The path is computed using BFS (via NetworkX's `shortest_path`), which guarantees the shortest route in this unweighted graph.
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
        _fig_path, ax_path = plt.subplots(figsize=(10, 7))
        pos_path = nx.spring_layout(G_path, seed=42)

        nx.draw_networkx_edges(G_path, pos_path, alpha=0.15, ax=ax_path)

        p_edges = list(zip(p[:-1], p[1:]))
        nx.draw_networkx_edges(G_path, pos_path, edgelist=p_edges, width=3, edge_color="#e03131", alpha=0.9, ax=ax_path)

        colors_path = []
        for node in G_path.nodes():
            if node == na:
                colors_path.append("#ff6b6b")
            elif node == nb:
                colors_path.append("#2b8a3e")
            elif node in p:
                colors_path.append("#ffc078")
            else:
                colors_path.append("lightblue")

        nx.draw_networkx_nodes(G_path, pos_path, node_color=colors_path, node_size=200, ax=ax_path)
        nx.draw_networkx_labels(G_path, pos_path, font_size=9, ax=ax_path)

        ax_path.set_title(f"Path {na} \u2192 {nb}: {p} (length: {pl})", fontsize=13)
        ax_path.axis("off")
        plt.tight_layout()
        output = mo.mpl.interactive(plt.gcf())
    else:
        output = mo.md(f"No path exists between node {na} and node {nb}")

    output
    return


@app.cell
def _(mo):
    mo.md("""
    ## Summary

    ### What You Learned

    | Concept | Why It Matters |
    |---------|---------------|
    | **BFS** | Level-by-level traversal. Finds shortest paths in unweighted graphs. Queue-based. |
    | **DFS** | Deep-first traversal. Great for cycle detection and topological sorting. Stack-based. |
    | **Shortest Paths** | BFS for unweighted, Dijkstra for weighted. The foundation of GPS and network routing. |
    | **Connected Components** | Finds isolated subgraphs. Used in fraud detection, image segmentation, and social network analysis. |

    All these algorithms run in **O(V + E)** time — they visit every node and edge once.

    **Next up**: How do we measure importance in a network? We'll explore **centrality metrics** — PageRank (how Google ranks pages), betweenness centrality (bridges in a network), and more.
    """)
    return


@app.cell
def _():
    return


if __name__ == "__main__":
    app.run()
