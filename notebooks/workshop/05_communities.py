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
    from networkx.algorithms.community import (
        greedy_modularity_communities,
        label_propagation_communities,
        girvan_newman,
    )
    from itertools import islice

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
    # Communities & Clustering

    Networks often have **community structure** — groups of nodes that are densely connected internally but sparsely connected to the rest of the network.

    ## What is a Community?

    > A **community** is a set of nodes that have more connections within the group than expected by chance.

    Real-world examples:
    - **Social networks**: Friend groups, families, colleagues
    - **Citation networks**: Research communities (ML, biology, physics)
    - **Biological networks**: Protein complexes, functional modules
    - **The web**: Pages on related topics
    """)
    return


@app.cell
def _(mo):
    mo.md(r"""
    ## Modularity: Measuring Community Quality

    **Modularity** (\(Q\)) is a score that measures how good a community division is:

    $$Q = \frac{1}{2m} \sum_{ij} \left[ A_{ij} - \frac{k_i k_j}{2m} \right] \delta(c_i, c_j)$$

    - \(A_{ij}\): adjacency matrix (1 if edge exists)
    - \(k_i\): degree of node \(i\)
    - \(m\): total number of edges
    - \(\delta(c_i, c_j)\): 1 if nodes are in same community, 0 otherwise

    **Key insight**: Modularity compares the actual number of edges within communities to the expected number in a random graph with the same degree distribution.

    - \(Q > 0\): More edges within groups than expected → community structure
    - \(Q > 0.3\): Generally considered significant
    - \(Q > 0.7\): Strong community structure
    """)
    return


@app.cell
def _(mo):
    mo.md("""
    ## Community Detection Algorithms

    We'll explore three popular algorithms:
    """)
    return


@app.cell
def _(mo):
    mo.md("""
    ### 1. Greedy Modularity (Clauset-Newman-Moore)

    **How it works**:
    1. Start with every node as its own community
    2. Repeatedly merge communities that increase modularity the most
    3. Stop when no merge improves modularity

    ✅ Fast (\(\mathcal{O}(n \log^2 n)\))
    ✅ Works well for many networks
    ❌ Can miss small communities (resolution limit)
    """)
    return


@app.cell
def _(mo):
    mo.md("""
    ### 2. Label Propagation

    **How it works**:
    1. Assign each node a unique label
    2. Repeatedly update each node's label to the most frequent label among its neighbors
    3. Converges when labels stop changing

    ✅ Very fast (\(\mathcal{O}(E)\) per iteration)
    ✅ No need to specify number of communities
    ❌ Can be unstable (different runs may give different results)
    """)
    return


@app.cell
def _(mo):
    mo.md("""
    ### 3. Girvan-Newman

    **How it works**:
    1. Compute edge betweenness for all edges
    2. Remove the edge with highest betweenness
    3. Recompute betweenness
    4. Repeat until graph is partitioned

    ✅ Hierarchical — shows communities at all scales
    ❌ Slow (\(\mathcal{O}(E^2 V)\)) — impractical for large graphs
    """)
    return


@app.cell
def _(mo):
    mo.md("""
    ## Let's See Them in Action

    We'll apply all three algorithms to Zachary's Karate Club — the classic benchmark for community detection.
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
    true_communities = {"Mr. Hi": [], "John A.": []}
    for n, club in G_kc.nodes(data="club"):
        true_communities[club].append(n)

    greedy_comms = list(greedy_modularity_communities(G_kc))
    lp_comms = list(label_propagation_communities(G_kc))

    fig_kc, axes_kc = plt.subplots(1, 3, figsize=(20, 6))
    pos_kc = nx.spring_layout(G_kc, seed=42)

    titles_kc = ["Ground Truth (Mr. Hi vs John A.)", "Greedy Modularity", "Label Propagation"]
    comms_list = [
        [set(v) for v in true_communities.values()],
        greedy_comms,
        lp_comms,
    ]

    community_colors = ["#ff6b6b", "#339af0", "#51cf66", "#cc5de8"]
    for ax, title, communities in zip(axes_kc, titles_kc, comms_list):
        node_color_map = {}
        for i, comm in enumerate(communities):
            for n in comm:
                node_color_map[n] = community_colors[i % len(community_colors)]
        colors = [node_color_map[n] for n in G_kc.nodes()]

        nx.draw_networkx_nodes(G_kc, pos_kc, node_color=colors, node_size=250, ax=ax)
        nx.draw_networkx_edges(G_kc, pos_kc, width=0.8, alpha=0.3, ax=ax)
        nx.draw_networkx_labels(G_kc, pos_kc, font_size=9, ax=ax)
        ax.set_title(title, fontsize=14)
        ax.axis("off")

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

        Both algorithms find the well-known split of the karate club!
        """
    )
    return


@app.cell
def _(mo):
    mo.md("""
    ## Interactive: Create Your Own Community Structure

    Generate a network with built-in communities and see how the algorithms detect them.
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
def _(
    algorithm,
    greedy_modularity_communities,
    label_propagation_communities,
    mo,
    n_communities,
    n_per_comm,
    np,
    nx,
    p_in,
    p_out,
    plt,
):
    np.random.seed(42)
    G_planted = nx.Graph()
    community_assignment = {}
    comm_sizes = [n_per_comm.value] * n_communities.value

    start = 0
    for i, size in enumerate(comm_sizes):
        nodes = list(range(start, start + size))
        for u in nodes:
            community_assignment[u] = i
            for v in nodes:
                if u < v and np.random.random() < p_in.value:
                    G_planted.add_edge(u, v)
        start += size

    all_nodes = list(G_planted.nodes())
    for i in range(len(comm_sizes)):
        for j in range(i + 1, len(comm_sizes)):
            nodes_i = [n for n in all_nodes if community_assignment[n] == i]
            nodes_j = [n for n in all_nodes if community_assignment[n] == j]
            for u in nodes_i:
                for v in nodes_j:
                    if np.random.random() < p_out.value:
                        G_planted.add_edge(u, v)

    if algorithm.value == "Greedy Modularity":
        detected_comms = list(greedy_modularity_communities(G_planted))
    else:
        detected_comms = list(label_propagation_communities(G_planted))

    planted_mod = nx.community.modularity(G_planted, [set([n for n in all_nodes if community_assignment[n] == i]) for i in range(n_communities.value)])
    detected_mod = nx.community.modularity(G_planted, detected_comms)

    comm_colors_plant = ["#ff6b6b", "#339af0", "#51cf66", "#cc5de8", "#f59f00"]
    fig_plant, (ax_true, ax_det) = plt.subplots(1, 2, figsize=(18, 7))
    pos_plant = nx.spring_layout(G_planted, seed=42, k=2)

    true_colors = [comm_colors_plant[community_assignment[n] % len(comm_colors_plant)] for n in G_planted.nodes()]
    nx.draw_networkx_nodes(G_planted, pos_plant, node_color=true_colors, node_size=200, ax=ax_true)
    nx.draw_networkx_edges(G_planted, pos_plant, width=0.5, alpha=0.3, ax=ax_true)
    ax_true.set_title(f"Ground Truth ({n_communities.value} communities, Q={planted_mod:.3f})", fontsize=13)
    ax_true.axis("off")

    detected_node_colors = {}
    for i, comm in enumerate(detected_comms):
        for n in comm:
            detected_node_colors[n] = comm_colors_plant[i % len(comm_colors_plant)]
    det_colors = [detected_node_colors.get(n, "gray") for n in G_planted.nodes()]
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
    ## Understanding the Parameters

    - **p_in (internal density)**: Higher values → tighter, more obvious communities
    - **p_out (external density)**: Higher values → communities blend together, harder to detect
    - **Communities are detectable** when \(p_{in} > p_{out}\)

    The **modularity** score tells you how well-defined the communities are:
    - \(Q > 0.3\): Good community structure
    - \(Q > 0.5\): Strong community structure
    - \(Q < 0.1\): Weak or no community structure
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
    | **Girvan-Newman** | Slow | Excellent | ✅ Yes | Small graphs, hierarchy |

    ### 💡 Pro Tips

    1. **Run multiple times** for label propagation and take the most common result
    2. **Modularity has a resolution limit** — it can miss small communities in large networks
    3. **Real communities overlap** — a person can belong to multiple groups (family, work, hobbies)
    4. **Hierarchical structure** exists in most real networks — communities contain sub-communities
    """)
    return


@app.cell
def _(mo):
    mo.md("""
    ## Real-World Application: Social Network Communities

    Let's look for communities in a larger network:
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

    fig_large, (ax_net, ax_dist) = plt.subplots(1, 2, figsize=(18, 6))
    pos_large = nx.spring_layout(G_large, seed=42, iterations=50)

    large_colors_list = ["#ff6b6b", "#339af0", "#51cf66", "#cc5de8", "#f59f00",
                         "#20c997", "#e64980", "#845ef7", "#fab005", "#7950f2"]
    node_to_comm = {}
    for i, comm in enumerate(comms_large):
        for n in comm:
            node_to_comm[n] = large_colors_list[i % len(large_colors_list)]
    node_colors_large = [node_to_comm[n] for n in G_large.nodes()]

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
    - **Modularity: {mo.as_html(mo.ui.stat("N/A" if mod_large is None else f"{mod_large:.3f}"))}**
    - **Largest community:** {max(comm_sizes_large)} nodes
    - **Smallest community:** {min(comm_sizes_large)} nodes

    In real-world networks like social media, communities often reveal:
    - Friend groups, interest clusters
    - Geographic regions
    - Organizational structures
    """)
    return


@app.cell
def _(mo):
    mo.md("""
    ## Summary

    ✅ **Communities** are groups of densely connected nodes
    ✅ **Modularity** measures how good a community division is
    ✅ **Greedy Modularity**: Fast, deterministic, good for most cases
    ✅ **Label Propagation**: Very fast, slightly less stable
    ✅ **Girvan-Newman**: Slow but reveals hierarchy
    ✅ Community structure is everywhere — from social networks to biology

    **Next up:** Advanced topics — graph embeddings, spectral methods, and Graph Neural Networks!
    """)
    return


@app.cell
def _():
    return


if __name__ == "__main__":
    app.run()
