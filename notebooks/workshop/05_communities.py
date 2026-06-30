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
    from networkx.algorithms.community import greedy_modularity_communities
    from networkx.algorithms.community import label_propagation_communities

    return (
        greedy_modularity_communities,
        label_propagation_communities,
        mo,
        np,
        nx,
        plt,
    )


@app.cell
def _(mo):
    mo.md("""
    # 05 — Communities & Clustering

    Networks often have **community structure** — groups of nodes that are densely connected internally but sparsely connected to the rest of the network.

    | # | Topic | What You'll Learn |
    |---|-------|-------------------|
    | 1 | **What Is a Community?** | Definition and real-world examples |
    | 2 | **Modularity** | Measuring how good a community division is |
    | 3 | **Greedy Modularity** | Fast, deterministic community detection |
    | 4 | **Label Propagation** | Very fast, near-linear algorithm |
    | 5 | **Interactive Simulator** | Create your own community structure |
    | 6 | **Real-World Application** | Communities in a large network |

    ---

    > **Analogy**: A university has departments (physics, biology, art). Within each department, people interact frequently. Across departments, interactions are rarer. The departments are **communities**.
    """)
    return


@app.cell
def _(mo):
    mo.md("""
    ## Topic 1: What Is a Community?

    > A **community** is a set of nodes that have more connections within the group than expected by chance.

    **Real-world examples**:
    - **Social networks**: Friend groups, families, colleagues
    - **Citation networks**: Research communities (ML, biology, physics)
    - **Biological networks**: Protein complexes, functional modules
    - **The web**: Pages on related topics

    **How to spot one**: In a graph visualization, communities look like clusters — dense regions with sparse connections between them.

    **Why it matters**: Community detection reveals hidden structure — market segments, disease modules, fraud rings, interest groups.
    """)
    return


@app.cell
def _(mo):
    mo.md(r"""
    ## Topic 2: Modularity — Measuring Community Quality

    **Modularity** (\(Q\)) is a score that measures how good a community division is:

    $$Q = \frac{1}{2m} \sum_{ij} \left[ A_{ij} - \frac{k_i k_j}{2m} \right] \delta(c_i, c_j)$$

    **Where**:
    - \(A_{ij}\): adjacency matrix (1 if edge exists)
    - \(k_i\): degree of node i
    - \(m\): total number of edges
    - \(\delta(c_i, c_j)\): 1 if nodes are in same community, 0 otherwise

    **How it works**: Compare the actual number of edges within communities to the expected number in a random graph with the same degree distribution.

    **Interpretation**:
    | Q | Meaning |
    |---|---------|
    | Q > 0 | More edges within groups than expected |
    | Q > 0.3 | Generally considered significant |
    | Q > 0.7 | Strong community structure |
    | Q < 0 | Worse than random — communities are misaligned |

    > **Analogy**: At a school, you'd expect students in the same club to talk more. Modularity checks: "Do drama club members actually talk to each other more than they talk to sports club members?"
    """)
    return


@app.cell
def _(mo):
    mo.md("""
    ## Topic 3: Greedy Modularity (Clauset-Newman-Moore)

    **How it works**:
    1. Start with every node as its own community (n communities for n nodes)
    2. At each step, merge the pair of communities that increases modularity the most
    3. Stop when no merge improves modularity

    **When to use**: General-purpose community detection.

    **Complexity**: O(n log² n) — scales well to medium-sized graphs (up to ~100K nodes).

    **Analogy**: Start with everyone at a party as their own group. If your group merges with another, the "vibe" (modularity) might go up or down. Keep merging groups that improve the vibe.

    > **Limitation**: Resolution limit — can miss small communities in large networks because merging two small communities has a tiny effect on modularity.
    """)
    return


@app.cell
def _(mo):
    mo.md("""
    ## Topic 4: Label Propagation

    **How it works**:
    1. Assign each node a unique label (its node ID)
    2. Repeatedly: for each node, update its label to the most frequent label among its neighbors
    3. Converges when labels stop changing (usually in 5–10 iterations)

    **When to use**: Very large graphs where speed matters more than stability.

    **Complexity**: O(E) per iteration — near-linear, scales to millions of edges.

    **Analogy**: Your friend group develops a shared accent or slang. If most of your friends say "y'all," you start saying it too. Over time, distinct linguistic communities emerge.

    > **Trade-off**: Fast and simple, but non-deterministic — different runs may give different results due to tie-breaking order.
    """)
    return


@app.cell
def _(mo):
    mo.md("""
    ## Communities in Action: Zachary's Karate Club

    The Karate Club is the classic benchmark for community detection. The club famously split into two factions (Mr. Hi's group and the Officer's group) after a dispute. Let's see if our algorithms recover this split.
    """)
    return


@app.cell
def _(
    greedy_modularity_communities,
    label_propagation_communities,
    mo,
    nx,
    plt,
):
    G_kc = nx.karate_club_graph()
    true_communities = {"Mr. Hi": [], "Officer": []}
    for _n, _club in G_kc.nodes(data="club"):
        true_communities[_club].append(_n)

    greedy_comms = list(greedy_modularity_communities(G_kc))
    lp_comms = list(label_propagation_communities(G_kc))

    _fig_kc, axes_kc = plt.subplots(1, 3, figsize=(20, 6))
    pos_kc = nx.spring_layout(G_kc, seed=42)

    titles_kc = ["Ground Truth (Mr. Hi vs Officer)", "Greedy Modularity", "Label Propagation"]
    comms_list = [
        [set(_v) for _v in true_communities.values()],
        greedy_comms,
        lp_comms,
    ]

    community_colors = ["#ff6b6b", "#339af0", "#51cf66", "#cc5de8"]
    for _ax, _title, _communities in zip(axes_kc, titles_kc, comms_list, strict=True):
        node_color_map = {}
        for _i, _comm in enumerate(_communities):
            for _n in _comm:
                node_color_map[_n] = community_colors[_i % len(community_colors)]
        colors = [node_color_map[_n] for _n in G_kc.nodes()]

        nx.draw_networkx_nodes(G_kc, pos_kc, node_color=colors, node_size=250, ax=_ax)
        nx.draw_networkx_edges(G_kc, pos_kc, width=0.8, alpha=0.3, ax=_ax)
        nx.draw_networkx_labels(G_kc, pos_kc, font_size=9, ax=_ax)
        _ax.set_title(_title, fontsize=14)
        _ax.axis("off")

    plt.tight_layout()
    mo.mpl.interactive(plt.gcf())
    return G_kc, greedy_comms, lp_comms


@app.cell
def _(G_kc, greedy_comms, lp_comms, mo, nx):
    greedy_mod = nx.community.modularity(G_kc, greedy_comms)
    lp_mod = nx.community.modularity(G_kc, lp_comms)

    mo.md(
        f"""
        **Modularity Scores:**
        - Greedy Modularity: {greedy_mod:.3f}
        - Label Propagation: {lp_mod:.3f}

        Both algorithms find the well-known split of the karate club! The modularity scores (both well above 0.3) confirm strong community structure.
        """
    )
    return


@app.cell
def _(mo):
    mo.md("""
    ## Topic 5: Interactive Community Simulator

    Generate a network with built-in communities and see how algorithms detect them. Adjust the sliders to make communities tight (high p_in) or blended (high p_out).
    """)
    return


@app.cell
def _(mo):
    n_per_comm = mo.ui.slider(5, 30, step=5, value=15, label="Nodes per community")
    p_in = mo.ui.slider(0.1, 1.0, step=0.1, value=0.6, label="Connection probability INSIDE community")
    p_out = mo.ui.slider(0.0, 0.5, step=0.02, value=0.05, label="Connection probability BETWEEN communities")
    n_communities = mo.ui.slider(2, 5, step=1, value=3, label="Number of communities")
    algorithm = mo.ui.dropdown(
        ["Greedy Modularity", "Label Propagation"],
        value="Greedy Modularity",
        label="Detection algorithm:",
    )

    mo.vstack([n_per_comm, p_in, p_out, n_communities, algorithm], gap=1)
    return algorithm, n_communities, n_per_comm, p_in, p_out


@app.cell
def _(n_communities, n_per_comm, np, nx, p_in, p_out):
    np.random.seed(42)
    G_planted = nx.Graph()
    community_assignment = {}
    sizes = [n_per_comm.value] * n_communities.value
    offset = 0
    for _i, _size in enumerate(sizes):
        nodes = list(range(offset, offset + _size))
        for u in nodes:
            community_assignment[u] = _i
            for v in nodes:
                if u < v and np.random.random() < p_in.value:
                    G_planted.add_edge(u, v)
        offset += _size
    all_nodes = list(G_planted.nodes())
    for _i in range(len(sizes)):
        for _j in range(_i + 1, len(sizes)):
            grp_i = [_n for _n in all_nodes if community_assignment[_n] == _i]
            grp_j = [_n for _n in all_nodes if community_assignment[_n] == _j]
            for u in grp_i:
                for v in grp_j:
                    if np.random.random() < p_out.value:
                        G_planted.add_edge(u, v)
    return G_planted, all_nodes, community_assignment


@app.cell
def _(
    G_planted,
    algorithm,
    all_nodes,
    community_assignment,
    greedy_modularity_communities,
    label_propagation_communities,
    mo,
    n_communities,
    nx,
    plt,
):

    if algorithm.value == "Greedy Modularity":
        detected_comms = list(greedy_modularity_communities(G_planted))
    else:
        detected_comms = list(label_propagation_communities(G_planted))

    planted_mod = nx.community.modularity(
        G_planted, [{_n for _n in all_nodes if community_assignment[_n] == _i} for _i in range(n_communities.value)]
    )
    detected_mod = nx.community.modularity(G_planted, detected_comms)

    comm_colors_plant = ["#ff6b6b", "#339af0", "#51cf66", "#cc5de8", "#f59f00"]
    _fig_plant, (ax_true, ax_det) = plt.subplots(1, 2, figsize=(18, 7))
    pos_plant = nx.spring_layout(G_planted, seed=42, k=2)

    true_colors = [comm_colors_plant[community_assignment[_n] % len(comm_colors_plant)] for _n in G_planted.nodes()]
    nx.draw_networkx_nodes(G_planted, pos_plant, node_color=true_colors, node_size=200, ax=ax_true)
    nx.draw_networkx_edges(G_planted, pos_plant, width=0.5, alpha=0.3, ax=ax_true)
    ax_true.set_title(f"Ground Truth ({n_communities.value} communities, Q={planted_mod:.3f})", fontsize=13)
    ax_true.axis("off")

    detected_node_colors = {}
    for _i, _comm in enumerate(detected_comms):
        for _n in _comm:
            detected_node_colors[_n] = comm_colors_plant[_i % len(comm_colors_plant)]
    det_colors = [detected_node_colors.get(_n, "gray") for _n in G_planted.nodes()]
    nx.draw_networkx_nodes(G_planted, pos_plant, node_color=det_colors, node_size=200, ax=ax_det)
    nx.draw_networkx_edges(G_planted, pos_plant, width=0.5, alpha=0.3, ax=ax_det)
    ax_det.set_title(f"Detected ({algorithm.value}, Q={detected_mod:.3f})", fontsize=13)
    ax_det.axis("off")

    plt.tight_layout()
    mo.mpl.interactive(plt.gcf())
    return


@app.cell
def _(mo):
    mo.md("""
    **Understanding the Parameters:**

    - **p_in (internal density)**: Higher → tighter, more obvious communities
    - **p_out (external density)**: Higher → communities blend together, harder to detect
    - **Communities are detectable** when p_in > p_out

    **Modularity Interpretation:**
    | Q | What It Means |
    |---|---------------|
    | Q > 0.3 | Good community structure |
    | Q > 0.5 | Strong community structure |
    | Q < 0.1 | Weak or no community structure |

    > **Pro tip**: If Q drops below 0.3 despite high p_in, the graph is too small or communities have too many external connections.
    """)
    return


@app.cell
def _(mo):
    mo.md("""
    ## Comparing Algorithms: When to Use What

    | Algorithm | Speed | Quality | Deterministic | Best For |
    |-----------|-------|---------|---------------|----------|
    | **Greedy Modularity** | Fast | Good | ✅ Yes | General purpose |
    | **Label Propagation** | Very fast | Good | ❌ No | Large-scale networks |

    **Girvan-Newman** (not shown here): Slow (O(E²V)) but reveals hierarchical community structure at all scales. Use it for small graphs (< 1000 nodes) where hierarchy matters.

    ### Pro Tips

    1. **Run label propagation multiple times** and take the most common result (since it's non-deterministic)
    2. **Modularity has a resolution limit** — it can miss small communities in large networks
    3. **Real communities overlap** — a person can belong to multiple groups (family, work, hobbies). Overlapping community detection is an active research area
    4. **Hierarchical structure** exists in most real networks — communities contain sub-communities
    """)
    return


@app.cell
def _(greedy_modularity_communities, mo, nx, plt):
    G_large = nx.barabasi_albert_graph(200, 3, seed=42)
    G_large = G_large.to_undirected()

    comms_large = list(greedy_modularity_communities(G_large))
    num_comms = len(comms_large)
    comm_sizes_large = [len(c) for c in comms_large]
    mod_large = nx.community.modularity(G_large, comms_large)

    _fig_large, (ax_net, ax_dist) = plt.subplots(1, 2, figsize=(18, 6))
    pos_large = nx.spring_layout(G_large, seed=42, iterations=50)

    large_colors_list = [
        "#ff6b6b",
        "#339af0",
        "#51cf66",
        "#cc5de8",
        "#f59f00",
        "#20c997",
        "#e64980",
        "#845ef7",
        "#fab005",
        "#7950f2",
    ]
    node_to_comm = {}
    for _i, _comm in enumerate(comms_large):
        for _n in _comm:
            node_to_comm[_n] = large_colors_list[_i % len(large_colors_list)]
    node_colors_large = [node_to_comm[_n] for _n in G_large.nodes()]

    nx.draw_networkx_nodes(G_large, pos_large, node_color=node_colors_large, node_size=50, alpha=0.8, ax=ax_net)
    nx.draw_networkx_edges(G_large, pos_large, width=0.3, alpha=0.15, ax=ax_net)
    ax_net.set_title(f"Detected Communities (Q={mod_large:.3f}, {num_comms} communities)", fontsize=13)
    ax_net.axis("off")

    ax_dist.bar(range(len(comm_sizes_large)), sorted(comm_sizes_large, reverse=True), color="steelblue")
    ax_dist.set_xlabel("Community Rank")
    ax_dist.set_ylabel("Community Size")
    ax_dist.set_title("Community Size Distribution")
    ax_dist.grid(alpha=0.3)

    plt.tight_layout()
    mo.mpl.interactive(plt.gcf())
    return comm_sizes_large, mod_large, num_comms


@app.cell
def _(comm_sizes_large, mo, mod_large, num_comms):
    mo.md(f"""
    **Community Detection Summary:**
    - **{num_comms} communities** found
    - **Modularity: {mod_large:.3f}**
    - **Largest community:** {max(comm_sizes_large)} nodes
    - **Smallest community:** {min(comm_sizes_large)} nodes

    In real-world networks like social media, communities often reveal:
    - Friend groups, interest clusters
    - Geographic regions
    - Organizational structures
    - Functional modules in biological systems
    """)
    return


@app.cell
def _(mo):
    mo.md("""
    ## Summary

    | # | You've Learned | Key Insight |
    |---|---------------|-------------|
    | 1 | **What communities are** | Dense internal connections, sparse external |
    | 2 | **Modularity** | Compares actual edges vs random expectation |
    | 3 | **Greedy Modularity** | Fast, deterministic, good default choice |
    | 4 | **Label Propagation** | Very fast, slightly unstable, great for scale |
    | 5 | **Interactive simulation** | Communities are detectable when p_in > p_out |

    > **Key insight**: Community structure is everywhere — from social networks to biology. The best algorithm depends on your graph size, whether you need deterministic results, and whether hierarchy matters.

    **Next up:** [06 — Advanced Topics](./06_advanced_topics.py) — graph embeddings, spectral methods, and Graph Neural Networks!
    """)
    return


if __name__ == "__main__":
    app.run()
