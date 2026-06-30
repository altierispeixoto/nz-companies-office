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
    # 04 — Centrality & Influence

    Not all nodes are equal. Some are more **important** or **central** than others. Centrality measures quantify this importance.

    | # | Topic | What You'll Learn |
    |---|-------|-------------------|
    | 1 | **Four Classic Measures** | Degree, Betweenness, Closeness, Eigenvector |
    | 2 | **Side-by-Side Comparison** | See all four on one network |
    | 3 | **Degree Centrality** | Counting connections |
    | 4 | **Betweenness Centrality** | Bridges and gatekeepers |
    | 5 | **Closeness Centrality** | Speed of information spread |
    | 6 | **Eigenvector Centrality & PageRank** | Influence and Google's algorithm |
    | 7 | **Interactive Explorer** | Apply measures to the Karate Club |

    ---

    > **Analogy**: In an organization, different people are important for different reasons — the CEO (power), the gossip (information flow), the only person who talks to both engineering and sales (bridge), the person everyone wants to impress (prestige).
    """)
    return


@app.cell
def _(mo):
    mo.md("""
    ## Topic 1: The Four Classic Centrality Measures

    | Measure | What It Measures | Real-World Question |
    |---------|-----------------|---------------------|
    | **Degree Centrality** | How many direct connections | "Who has the most friends?" |
    | **Betweenness Centrality** | How often a node lies on paths between others | "Who is the bridge between groups?" |
    | **Closeness Centrality** | How close a node is to all others | "Who can spread information fastest?" |
    | **Eigenvector Centrality** | How important are the node's connections | "Who knows the most important people?" |

    > **Key insight**: Different questions need different measures. The most connected person (degree) isn't necessarily the best bridge (betweenness) or the most influential (eigenvector).
    """)
    return


@app.cell
def _(mo):
    mo.md("""
    ## Topic 2: Side-by-Side Comparison

    We'll build a network with three friend groups (cliques) connected by a few bridge nodes. This design highlights how each measure assigns importance differently.
    """)
    return


@app.cell
def _(mo, np, nx, plt):
    G_comp = nx.Graph()

    clique_a = range(6)
    clique_b = range(6, 11)
    clique_c = range(11, 16)

    for clique in [clique_a, clique_b, clique_c]:
        nodes = list(clique)
        for i in range(len(nodes)):
            for j in range(i + 1, len(nodes)):
                G_comp.add_edge(nodes[i], nodes[j])

    G_comp.add_edge(5, 6)
    G_comp.add_edge(5, 11)
    G_comp.add_edge(10, 11)

    deg_cent = nx.degree_centrality(G_comp)
    btw_cent = nx.betweenness_centrality(G_comp)
    clo_cent = nx.closeness_centrality(G_comp)
    eig_cent = nx.eigenvector_centrality(G_comp, max_iter=1000)

    _fig_comp, axes_comp = plt.subplots(2, 2, figsize=(16, 14))
    pos_comp = nx.spring_layout(G_comp, seed=42, k=2)

    titles = ["Degree Centrality", "Betweenness Centrality", "Closeness Centrality", "Eigenvector Centrality"]
    cent_data = [deg_cent, btw_cent, clo_cent, eig_cent]
    cmaps = ["Oranges", "Reds", "Purples", "Greens"]

    for ax, title, cent, _cmap_name in zip(axes_comp.flat, titles, cent_data, cmaps, strict=True):
        _vals = np.array(list(cent.values()))
        node_colors = plt.cm.get_cmap(_cmap_name)((_vals - _vals.min()) / (_vals.max() - _vals.min() + 1e-10))
        nx.draw_networkx_nodes(G_comp, pos_comp, node_color=node_colors, node_size=600, ax=ax)
        nx.draw_networkx_edges(G_comp, pos_comp, width=1.5, alpha=0.5, ax=ax)
        nx.draw_networkx_labels(G_comp, pos_comp, ax=ax)
        ax.set_title(title, fontsize=14)
        ax.axis("off")

    plt.tight_layout()
    mo.mpl.interactive(plt.gcf())
    return btw_cent, clo_cent, deg_cent, eig_cent


@app.cell
def _(btw_cent, clo_cent, deg_cent, eig_cent, mo):
    rows = [
        {
            "Node": str(node),
            "Degree": f"{deg_cent[node]:.3f}",
            "Betweenness": f"{btw_cent[node]:.3f}",
            "Closeness": f"{clo_cent[node]:.3f}",
            "Eigenvector": f"{eig_cent[node]:.3f}",
        }
        for node in deg_cent
    ]

    mo.ui.table(rows)
    return


@app.cell
def _(mo):
    mo.md(r"""
    ## Topic 3: Degree Centrality

    **Formula**: $$\text{Degree}(v) = \frac{\text{number of neighbors of }v}{n - 1}$$

    **What it measures**: How many direct connections a node has.

    **How it works**: Count the node's neighbors, divide by the maximum possible (n-1). Normalized to [0, 1].

    **When to use**: Quick popularity check. "Who has the most followers?"

    > **Strengths**: Simple, intuitive, O(V) to compute all nodes.
    > **Weaknesses**: Only considers LOCAL importance. A node connected to 10 nobodies scores as high as one connected to 10 influential people.

    **Analogy**: At a conference, degree centrality counts how many people you've met. It doesn't care who they are.
    """)
    return


@app.cell
def _(deg_cent, mo, plt):
    sorted_by_deg = sorted(deg_cent.items(), key=lambda x: x[1], reverse=True)

    _fig_deg, ax_deg = plt.subplots(figsize=(12, 4))
    nodes_str = [str(n) for n, _ in sorted_by_deg]
    vals = [v for _, v in sorted_by_deg]
    colors_deg = ["#e03131" if n == 5 else "#ffa94d" for n, _ in sorted_by_deg]
    ax_deg.bar(nodes_str, vals, color=colors_deg)
    ax_deg.set_xlabel("Node")
    ax_deg.set_ylabel("Degree Centrality")
    ax_deg.set_title("Degree Centrality — Node 5 (bridge) has highest degree")
    ax_deg.tick_params(axis="x", rotation=45)
    plt.tight_layout()
    mo.mpl.interactive(plt.gcf())
    return


@app.cell
def _(mo):
    mo.md(r"""
    ## Topic 4: Betweenness Centrality

    **Formula**: $$\text{Betweenness}(v) = \sum_{s \neq v \neq t} \frac{\sigma_{st}(v)}{\sigma_{st}}$$

    where \(\sigma_{st}\) is the total number of shortest paths from s to t, and \(\sigma_{st}(v)\) is the number that pass through v.

    **What it measures**: How often a node lies on the shortest path between other pairs.

    **How it works**: For every pair of nodes (s, t), compute shortest paths. Count how many go through v. Sum up. Normalize.

    **When to use**: Finding bridges, gatekeepers, bottlenecks. "Who connects different groups?"

    > **Strengths**: Captures structural importance — the "if this person leaves, information stops flowing" factor.
    > **Weaknesses**: Expensive to compute — O(VE) for unweighted, O(V³) for weighted.

    **Analogy**: The person who connects different friend groups at a party — without them, news from group A never reaches group B.
    """)
    return


@app.cell
def _(btw_cent, mo, plt):
    sorted_by_btw = sorted(btw_cent.items(), key=lambda x: x[1], reverse=True)

    _fig_btw, ax_btw = plt.subplots(figsize=(12, 4))
    nodes_str_btw = [str(n) for n, _ in sorted_by_btw]
    vals_btw = [v for _, v in sorted_by_btw]
    colors_btw = ["#e03131" if n == 5 else "#ffa94d" for n, _ in sorted_by_btw]
    ax_btw.bar(nodes_str_btw, vals_btw, color=colors_btw)
    ax_btw.set_xlabel("Node")
    ax_btw.set_ylabel("Betweenness Centrality")
    ax_btw.set_title("Betweenness Centrality — Node 5 dominates as the bridge between cliques")
    ax_btw.tick_params(axis="x", rotation=45)
    plt.tight_layout()
    mo.mpl.interactive(plt.gcf())
    return


@app.cell
def _(mo):
    mo.md(r"""
    ## Topic 5: Closeness Centrality

    **Formula**: $$\text{Closeness}(v) = \frac{n - 1}{\sum_{u \neq v} d(v, u)}$$

    where \(d(v, u)\) is the shortest path distance between v and u.

    **What it measures**: How quickly a node can reach everyone else.

    **How it works**: Compute shortest paths from v to all other nodes. Sum the distances. Divide (n-1) by that sum.

    **When to use**: Measuring information spread speed, efficiency of a node's location. "Who can get a message to everyone fastest?"

    > **Strengths**: Captures geographic centrality — centrally located nodes are close to everyone.
    > **Weaknesses**: Fails in disconnected graphs (infinite distance). Biased toward nodes in dense regions.

    **Analogy**: A cafe at a central intersection vs one in a remote suburb. The central cafe is "closer" to all possible customers on average.
    """)
    return


@app.cell
def _(clo_cent, mo, plt):
    sorted_by_clo = sorted(clo_cent.items(), key=lambda x: x[1], reverse=True)

    _fig_clo, ax_clo = plt.subplots(figsize=(12, 4))
    nodes_str_clo = [str(n) for n, _ in sorted_by_clo]
    vals_clo = [v for _, v in sorted_by_clo]
    colors_clo = ["#e03131" if n == 5 else "#b197fc" for n, _ in sorted_by_clo]
    ax_clo.bar(nodes_str_clo, vals_clo, color=colors_clo)
    ax_clo.set_xlabel("Node")
    ax_clo.set_ylabel("Closeness Centrality")
    ax_clo.set_title("Closeness Centrality — Bridge nodes are close to everyone")
    ax_clo.tick_params(axis="x", rotation=45)
    plt.tight_layout()
    mo.mpl.interactive(plt.gcf())
    return


@app.cell
def _(mo):
    mo.md(r"""
    ## Topic 6: Eigenvector Centrality & PageRank

    **Eigenvector centrality** doesn't just count your connections — it measures **who you're connected to**.

    **Formula**: $$x_v = \frac{1}{\lambda} \sum_{t \in N(v)} x_t$$

    **What it measures**: A node is important if it's connected to other important nodes.

    **How it works**: Solve for the principal eigenvector of the adjacency matrix. The centrality of each node is proportional to the sum of the centralities of its neighbors. This is a self-consistent definition — it's solved iteratively.

    **When to use**: Measuring influence, prestige, or "importance by association." "Who knows the most influential people?"

    **Analogy**: You might not know many people, but if those people are the CEO, the mayor, and the president — you're influential.

    ### PageRank: Eigenvector for the Web

    Google's PageRank adapts eigenvector centrality for the directed web graph:

    $$\text{PR}(v) = \frac{1 - d}{n} + d \sum_{u \in N_{in}(v)} \frac{\text{PR}(u)}{\text{deg}_{\text{out}}(u)}$$

    **Key differences from eigenvector centrality**:
    1. **Directed edges** — links from page u to page v, not symmetric
    2. **Damping factor** (d ≈ 0.85) — simulates random surfing; with probability 1-d, jump to a random page instead of following a link
    3. **Degree normalization** — a page's vote is divided by its out-degree (pages with many links spread their influence thinner)

    > **The insight**: PageRank is the probability distribution of where a random surfer ends up after clicking forever, occasionally jumping to a random page.
    """)
    return


@app.cell
def _(mo, np, nx, plt):
    G_pagerank = nx.DiGraph()
    G_pagerank.add_edges_from(
        [
            ("A", "B"),
            ("A", "C"),
            ("B", "C"),
            ("C", "A"),
            ("D", "C"),
            ("D", "E"),
            ("E", "C"),
            ("F", "C"),
            ("G", "A"),
            ("G", "D"),
            ("G", "E"),
            ("G", "F"),
            ("H", "A"),
            ("H", "D"),
            ("H", "E"),
            ("H", "F"),
            ("I", "A"),
            ("I", "D"),
            ("I", "E"),
            ("I", "F"),
        ]
    )

    pr = nx.pagerank(G_pagerank, alpha=0.85)
    pr_sorted = sorted(pr.items(), key=lambda x: x[1], reverse=True)

    _fig_pr, (ax_pr1, ax_pr2) = plt.subplots(1, 2, figsize=(16, 6))

    pos_pr = nx.spring_layout(G_pagerank, seed=42, k=2)
    pr_vals = np.array(list(pr.values()))
    pr_colors = plt.cm.YlOrRd((pr_vals - pr_vals.min()) / (pr_vals.max() - pr_vals.min() + 1e-10))
    nx.draw_networkx_nodes(G_pagerank, pos_pr, node_color=pr_colors, node_size=1200, ax=ax_pr1)
    nx.draw_networkx_edges(
        G_pagerank, pos_pr, width=1.5, alpha=0.5, ax=ax_pr1, arrows=True, arrowsize=20, connectionstyle="arc3,rad=0.1"
    )
    nx.draw_networkx_labels(G_pagerank, pos_pr, font_size=12, font_weight="bold", ax=ax_pr1)
    ax_pr1.set_title("PageRank Scores (node color = importance)", fontsize=14)
    ax_pr1.axis("off")

    nodes_pr = [str(n) for n, _ in pr_sorted]
    vals_pr = [v for _, v in pr_sorted]
    ax_pr2.bar(nodes_pr, vals_pr, color="tomato")
    ax_pr2.set_xlabel("Page")
    ax_pr2.set_ylabel("PageRank Score")
    ax_pr2.set_title("PageRank — which page is most important?")
    plt.tight_layout()
    mo.mpl.interactive(plt.gcf())
    return


@app.cell
def _(mo):
    mo.md("""
    ## Topic 7: Interactive Explorer — Karate Club

    Apply all four measures (plus PageRank) to Zachary's Karate Club. See how each measure highlights **different** nodes as important.
    """)
    return


@app.cell
def _(mo):
    centrality_choice = mo.ui.dropdown(
        ["Degree", "Betweenness", "Closeness", "Eigenvector", "PageRank"],
        value="Betweenness",
        label="Centrality measure:",
    )
    centrality_choice
    return (centrality_choice,)


@app.cell
def _(centrality_choice, mo, np, nx, plt):
    G_kc = nx.karate_club_graph()

    if centrality_choice.value == "Degree":
        cent_kc = nx.degree_centrality(G_kc)
        cmap_name = "Oranges"
    elif centrality_choice.value == "Betweenness":
        cent_kc = nx.betweenness_centrality(G_kc)
        cmap_name = "Reds"
    elif centrality_choice.value == "Closeness":
        cent_kc = nx.closeness_centrality(G_kc)
        cmap_name = "Purples"
    else:
        if centrality_choice.value == "PageRank":
            cent_kc = nx.pagerank(G_kc, alpha=0.85)
        else:
            cent_kc = nx.eigenvector_centrality(G_kc, max_iter=1000)
        cmap_name = "Greens"

    vals_kc = np.array(list(cent_kc.values()))
    norm_kc = (vals_kc - vals_kc.min()) / (vals_kc.max() - vals_kc.min() + 1e-10)
    colors_kc = plt.cm.get_cmap(cmap_name)(norm_kc)

    _fig_kc, (ax_kc1, ax_kc2) = plt.subplots(1, 2, figsize=(18, 6))
    pos_kc = nx.spring_layout(G_kc, seed=42)

    nx.draw_networkx_nodes(G_kc, pos_kc, node_color=colors_kc, node_size=500, ax=ax_kc1)
    nx.draw_networkx_edges(G_kc, pos_kc, width=1, alpha=0.3, ax=ax_kc1)
    nx.draw_networkx_labels(G_kc, pos_kc, font_size=10, ax=ax_kc1)
    ax_kc1.set_title(f"{centrality_choice.value} Centrality — Karate Club", fontsize=14)
    ax_kc1.axis("off")

    sorted_kc = sorted(cent_kc.items(), key=lambda x: x[1], reverse=True)
    top10_kc = sorted_kc[:10]
    nodes_bar = [str(n) for n, _ in top10_kc]
    vals_bar = [v for _, v in top10_kc]
    ax_kc2.barh(range(len(nodes_bar)), vals_bar, color="steelblue")
    ax_kc2.set_yticks(range(len(nodes_bar)))
    ax_kc2.set_yticklabels(nodes_bar)
    ax_kc2.set_xlabel(f"{centrality_choice.value} Centrality")
    ax_kc2.set_title(f"Top 10 Nodes by {centrality_choice.value} Centrality")
    ax_kc2.invert_yaxis()

    plt.tight_layout()
    mo.mpl.interactive(plt.gcf())
    return (sorted_kc,)


@app.cell
def _(centrality_choice, mo, sorted_kc):
    mo.md(f"""
    **Top 5 nodes by {centrality_choice.value} Centrality:**

    {", ".join(f"Node {n} ({v:.3f})" for n, v in sorted_kc[:5])}

    **Why different measures give different answers:**
    - **Degree** favors nodes with many friends (popularity)
    - **Betweenness** favors bridges between groups
    - **Closeness** favors centrally located nodes
    - **Eigenvector/PageRank** favors nodes connected to other important nodes
    """)
    return


@app.cell
def _(mo):
    mo.md("""
    ## Summary

    | # | You've Learned | When to Use |
    |---|---------------|-------------|
    | 1 | **Degree Centrality** | Quick popularity check — "most friends" |
    | 2 | **Betweenness Centrality** | Finding bridges and gatekeepers |
    | 3 | **Closeness Centrality** | Information spread speed |
    | 4 | **Eigenvector Centrality** | Influence and prestige |
    | 5 | **PageRank** | Web search and directed graphs |

    > **Key insight**: There's no single "most important node." Each measure answers a different question about importance.

    **Next up:** [05 — Communities & Clustering](./05_communities.py) — finding groups, detecting communities, and modularity.
    """)
    return


if __name__ == "__main__":
    app.run()
