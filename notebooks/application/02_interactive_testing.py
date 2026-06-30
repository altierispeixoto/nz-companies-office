# ---
# marimo-version: 0.23.9
# license: Apache-2.0
# ---

import marimo

__generated_with = "0.23.10"
app = marimo.App(width="full")


@app.cell
def _(mo):
    mo.md("""
    # NZ Companies Office — Interactive Testing

    This notebook lets you explore the trained link-prediction model interactively.
    It is split into several sections:

    1. **Setup** — imports and device configuration.
    2. **Data & Model** — loads the pipeline graph and trained model checkpoint.
    3. **Company Analysis** — pick a company to see its existing shareholders
       and which shareholders the model predicts should invest in it.
    4. **Edge Ablation** — pick a shareholder, remove all their investment edges,
       and see whether the model can reconstruct those investments using only
       structural signals (directors, industry codes). Also shows novel
       recommendations from the *full* model.
    """)
    return


@app.cell
def _(mo):
    mo.md("""
    ## 1. Setup
    """)
    return


@app.cell
def _():
    """Import libraries and configure the compute device."""
    import pathlib

    import marimo as mo
    import torch
    from torch.nn import functional as F  # noqa: N812

    from nz_companies_office.models.link_predictor import LinkPredictor
    from nz_companies_office.utils.device import get_device

    # Select GPU if sufficient free memory (>512 MiB), else fall back to CPU
    device = get_device()
    return F, LinkPredictor, device, mo, pathlib, torch


@app.cell
def _(mo):
    mo.md("""
    ## 2. Data & Model

    Loads the full-company graph (HeteroData) from the pipeline checkpoint,
    then initialises the trained model and pre-computes embeddings for all
    shareholder and company nodes. These embeddings are reused in the
    interactive sections below.
    """)
    return


@app.cell
def _(mo, pathlib, torch):
    """Load the pipeline checkpoint containing the graph structure and metadata."""
    pipeline_path = pathlib.Path("data/processed/pipeline_checkpoint/pipeline.pt")
    if pipeline_path.exists():
        _ckpt = torch.load(pipeline_path, map_location="cpu", weights_only=False)
        data = _ckpt["data"]  # full-graph HeteroData (test split with all edges)

        # Feature dimensions for initialising the model
        n_company_feats = _ckpt["n_company_feats"]
        n_director_feats = _ckpt["n_director_feats"]
        n_shareholder_feats = _ckpt["n_shareholder_feats"]
        n_industry_feats = _ckpt.get("n_industry_feats", 0)

        # Industry metadata (backward-compatible, empty if checkpoint was old)
        industry_codes = _ckpt.get("industry_codes", [])
        industry_descriptions = _ckpt.get("industry_descriptions", [])

        # Fallback: load industry metadata from the extractor cache
        # when the pipeline checkpoint predates the industry-metadata save
        if not industry_codes:
            extractor_path = pathlib.Path("data/processed/nz_companies.pt")
            if extractor_path.exists():
                _extracted = torch.load(extractor_path, map_location="cpu", weights_only=False)
                industry_codes = _extracted.get("industry_codes", [])
                industry_descriptions = _extracted.get("industry_descriptions", [])
    else:
        mo.output.append(mo.md("⚠️ **No pipeline checkpoint**. Run the main training notebook first."))
        data = None
        n_company_feats = None
        n_director_feats = None
        n_shareholder_feats = None
        n_industry_feats = 0
        industry_codes = []
        industry_descriptions = []
    return (
        data,
        industry_codes,
        industry_descriptions,
        n_company_feats,
        n_director_feats,
        n_industry_feats,
        n_shareholder_feats,
    )


@app.cell
def _(
    LinkPredictor,
    data,
    device,
    mo,
    n_company_feats,
    n_director_feats,
    n_industry_feats,
    n_shareholder_feats,
    pathlib,
    torch,
):
    """Load the trained model checkpoint and pre-encode the full graph."""
    model_ckpt_path = pathlib.Path("data/processed/model_checkpoint.pt")
    if model_ckpt_path.exists() and data is not None:
        model = LinkPredictor(
            n_director_feats,
            n_company_feats,
            n_shareholder_feats,
            ind_feats=n_industry_feats,
        ).to(device)
        model.load_state_dict(torch.load(model_ckpt_path, map_location=device, weights_only=True))
        model.eval()

        # Encode the full graph once → pre-computed embeddings for all nodes
        with torch.no_grad():
            _x_dict = model.encode(data)
            z_share = _x_dict["shareholder"]
            z_comp = _x_dict["company"]

        n_comp = z_comp.shape[0]
        n_share = z_share.shape[0]

        # Human-readable names (fall back to index labels if unavailable)
        try:
            comp_names = list(data["company"].names)
        except (AttributeError, KeyError):
            comp_names = [f"Company #{i}" for i in range(n_comp)]
        try:
            share_names = list(data["shareholder"].names)
        except (AttributeError, KeyError):
            share_names = [f"Shareholder #{i}" for i in range(n_share)]

        share_edge_index = data["shareholder", "share", "company"].edge_index
        comp_name_to_idx = {name: i for i, name in enumerate(comp_names)}
    else:
        if data is None:
            mo.output.append(mo.md("⚠️ **Pipeline checkpoint not loaded**."))
        else:
            mo.output.append(mo.md("⚠️ **No model checkpoint found** at `data/processed/model_checkpoint.pt`."))
        model = None
        z_share = None
        z_comp = None
        comp_names = None
        share_names = None
        comp_name_to_idx = None
        share_edge_index = None
    return (
        comp_name_to_idx,
        comp_names,
        model,
        share_edge_index,
        share_names,
        z_comp,
        z_share,
    )


@app.cell
def _(mo):
    mo.md("""
    ## 3. Company Analysis 🔍

    Search for a company by name, then select it from the dropdown. The panel
    shows:

    - **Existing shareholders** — who currently invests in this company.
    - **Top predicted shareholders** — the top-30 shareholders the model
      believes should invest, ranked by probability. The table includes
      similarity metrics to existing shareholders and co-investment
      information to help you understand *why* the model makes each prediction.
    """)
    return


@app.cell
def _(mo):
    """Text input for filtering the company dropdown by name."""
    search_input = mo.ui.text(label="Search companies", placeholder="Type name to filter...")
    search_input
    return (search_input,)


@app.cell
def _(comp_names, mo, search_input):
    """Dropdown listing companies that match the search query (max 200)."""
    if comp_names is None:
        company_selector = mo.md("⚠️ No companies loaded — run the training pipeline first.")
    else:
        query = search_input.value.strip().lower()
        filtered = [n for n in comp_names if query in n.lower()][:200] if query else comp_names[:200]

        if not filtered:
            company_selector = mo.md("*No matching companies found.*")
        else:
            company_selector = mo.ui.dropdown(
                options=filtered,
                value=filtered[0],
                label="Select a company",
            )
    company_selector
    return (company_selector,)


@app.cell
def _(
    F,
    comp_name_to_idx,
    comp_names,
    company_selector,
    data,
    mo,
    share_names,
    torch,
    z_comp,
    z_share,
):
    """Show existing and top predicted shareholders for a selected company."""
    if z_share is not None and z_comp is not None and hasattr(company_selector, "value"):
        company = company_selector.value
        comp_idx = comp_name_to_idx[company]

        # --- existing shareholders of this company ------------------------------
        _share_edges = data["shareholder", "share", "company"].edge_index
        existing_mask = _share_edges[1] == comp_idx
        existing_ids = _share_edges[0][existing_mask]
        existing_rows = [{"Shareholder": share_names[i.item()]} for i in existing_ids]

        # --- top predicted shareholders (full model) ----------------------------
        logits = z_share @ z_comp[comp_idx]
        probs = torch.sigmoid(logits)
        _top_k = 30
        _top_indices = probs.argsort(descending=True)[:_top_k]

        _avg_sim = []
        _best_existing = []
        _coinvest = []
        if existing_ids.numel() > 0:
            existing_all = _share_edges[1][torch.isin(_share_edges[0], existing_ids)]
            existing_coinvest_set = set(existing_all.tolist())
            existing_ids_dev = existing_ids.to(z_share.device)
            z_share_norm = F.normalize(z_share, p=2, dim=1)
        for idx in _top_indices:
            s = idx.item()
            if existing_ids.numel() > 0:
                sim_to_all = z_share_norm[s] @ z_share_norm[existing_ids_dev].T
                _avg_sim.append(f"{sim_to_all.mean().item():.3f}")
                best = sim_to_all.argmax()
                _best_existing.append(share_names[existing_ids_dev[best].item()])

                recom_comps = set(_share_edges[1][_share_edges[0] == s].tolist())
                common = recom_comps & existing_coinvest_set
                common_names = [comp_names[c] for c in sorted(common)[:5]]
                _coinvest.append(", ".join(common_names) if common_names else "—")
            else:
                _avg_sim.append("—")
                _best_existing.append("—")
                _coinvest.append("—")

        _pred_rows = [
            {
                "Rank": r + 1,
                "Shareholder": share_names[i.item()],
                "Probability": f"{probs[i].item():.4f}",
                "Avg sim to existing": _avg_sim[r],
                "Closest existing": _best_existing[r],
                "Co-invests with existing in": _coinvest[r],
            }
            for r, i in enumerate(_top_indices)
        ]

        output = mo.hstack(
            [
                mo.vstack(
                    [
                        mo.md(f"### {company} — Existing shareholders ({len(existing_rows)})"),
                        mo.ui.table(existing_rows, selection=None),
                    ],
                ),
                mo.vstack(
                    [
                        mo.md("### Top predicted shareholders"),
                        mo.ui.table(_pred_rows, selection=None),
                    ],
                ),
            ],
            gap=2,
        )
    else:
        output = None
    output
    return


@app.cell
def _(mo):
    mo.md("""
    ## 4. Edge Ablation Analysis 🧪

    **What it does:** selects a shareholder, clones the graph, and removes all
    of that shareholder's investment edges. The model re-encodes the
    shareholder from scratch using only its remaining connections (director
    relationships, industry codes, etc.).

    **Two output panels:**

    - *Left — Reconstructed investments* — for each company the shareholder
      actually invests in, shows where that company ranks in the *ablated*
      model's scores. A low rank (e.g. #5) means the model could reconstruct
      the investment from structural signals alone. A high rank means the
      model relied heavily on the investment-edge signal that was removed.

    - *Right — Top novel predictions* — the top companies the *full* (non-ablated)
      model would recommend to this shareholder, filtering out companies they
      already invest in. Useful for identifying new investment opportunities.

    **Search for a shareholder below to begin.**
    """)
    return


@app.cell
def _(mo):
    """Text input for filtering the shareholder dropdown by name."""
    share_search = mo.ui.text(label="Search shareholders", placeholder="Type name to filter...")
    share_search
    return (share_search,)


@app.cell
def _(mo, share_names, share_search):
    """Dropdown listing shareholders that match the search query (max 200)."""
    if share_names is None:
        share_selector = mo.md("⚠️ No shareholders loaded.")
    else:
        share_query = share_search.value.strip().lower()
        share_filtered = [n for n in share_names if share_query in n.lower()][:200] if share_query else []
        if not share_filtered:
            share_selector = mo.md(
                "*No matching shareholders found.*" if share_query else "🔍 Type above to search for a shareholder"
            )
        else:
            share_selector = mo.ui.dropdown(
                options=share_filtered,
                value=share_filtered[0],
                label="Select a shareholder to ablate",
            )
    share_selector
    return (share_selector,)


@app.cell
def _(
    comp_names,
    data,
    device,
    industry_codes,
    industry_descriptions,
    mo,
    model,
    share_edge_index,
    share_names,
    share_selector,
    torch,
    z_comp,
    z_share,
):
    """Ablate shareholder edges and display reconstruction + full-model predictions."""
    if (
        model is None
        or not hasattr(share_selector, "value")
        or share_selector.value is None
        or share_selector.value == ""
    ):
        abl_output = mo.md("⚠️ Load a model and select a shareholder above.")
    else:
        share_idx = share_names.index(share_selector.value)

        # ── identify known investments ────────────────────────────────────────
        inv_mask = share_edge_index[0] == share_idx
        existing_comp_indices = share_edge_index[1][inv_mask].unique()
        existing_set = set(existing_comp_indices.tolist())
        n_investments = len(existing_comp_indices)

        # ── industry-name lookup helper ────────────────────────────────────────
        if not industry_codes or ("company", "has_industry", "industry") not in data.edge_types:
            _ind_edges = None
        else:
            _ind_edges = data["company", "has_industry", "industry"].edge_index

        def _industry_names(comp_idx: int) -> str:
            if _ind_edges is None or _ind_edges.numel() == 0:
                return ""
            _mask = _ind_edges[0] == comp_idx
            _names = [
                industry_descriptions[int(i)]
                for i in _ind_edges[1, _mask].tolist()
                if int(i) < len(industry_descriptions)
            ]
            return ", ".join(_names[:2])

        if n_investments == 0:
            abl_output = mo.md(f"**{share_names[share_idx]}** has no known investments to reconstruct.")
        else:
            # ── ABLATION: re-encode graph with shareholder's edges removed ────
            keep_mask = share_edge_index[0] != share_idx
            ablated_data = data.clone()
            ablated_edges = share_edge_index[:, keep_mask]
            ablated_data["shareholder", "share", "company"].edge_index = ablated_edges
            ablated_data["company", "rev_share", "shareholder"].edge_index = ablated_edges[[1, 0]]

            model.eval()
            with torch.no_grad():
                ablated_z = model.encode(ablated_data.to(device))
                z_share_abl = ablated_z["shareholder"][share_idx]
                z_comp_abl = ablated_z["company"]

            # Score every company with the ablated embedding
            abl_logits = z_share_abl @ z_comp_abl.T
            abl_probs = torch.sigmoid(abl_logits)
            abl_rank_order = abl_probs.argsort(descending=True)
            abl_rank_map = torch.full((len(comp_names),), -1, dtype=torch.long, device=device)
            abl_rank_map[abl_rank_order] = torch.arange(len(comp_names), device=device)

            # ── reconstruction table — rank of each known investment ──────────
            invested_ranks = abl_rank_map[existing_comp_indices].cpu().numpy()
            reconstruction_rows = [
                {
                    "Company": comp_names[c.item()],
                    "Rank": int(invested_ranks[i]) + 1,
                    "Industry": _industry_names(c.item()),
                    "Probability": f"{abl_probs[c.item()]:.4f}",
                    "Reconstructed": "✅" if invested_ranks[i] < 50 else "—",
                }
                for i, c in enumerate(existing_comp_indices)
            ]
            reconstruction_rows.sort(key=lambda r: r["Rank"])

            invested_ranks_t = torch.as_tensor(invested_ranks)
            top_10_recall = (invested_ranks_t < 10).float().mean().item()
            top_50_recall = (invested_ranks_t < 50).float().mean().item()
            median_rank = int(invested_ranks_t.median().item()) + 1

            # ── FULL MODEL: top novel predictions ─────────────────────────────
            full_logits = z_share[share_idx] @ z_comp.T
            full_probs = torch.sigmoid(full_logits)
            full_rank_order = full_probs.argsort(descending=True)
            top_novel = [i for i in full_rank_order.tolist() if i not in existing_set][:20]

            top_rows = [
                {
                    "Rank": r + 1,
                    "Company": comp_names[i],
                    "Industry": _industry_names(i),
                    "Probability": f"{full_probs[i].item():.4f}",
                }
                for r, i in enumerate(top_novel)
            ]

            # ── assemble output panels ────────────────────────────────────────
            abl_output = mo.hstack(
                [
                    mo.vstack(
                        [
                            mo.md(f"### Edge Ablation: {share_names[share_idx]}"),
                            mo.md(
                                f"Removed **{n_investments}** investment"
                                f"{'s' if n_investments > 1 else ''} and re-encoded."
                            ),
                            mo.md(
                                f"**Median rank** of removed companies: **#{median_rank}**  \n"
                                f"**Top-10 recall**: {top_10_recall:.0%}  \n"
                                f"**Top-50 recall**: {top_50_recall:.0%}"
                            ),
                            mo.md("#### Reconstructed investments (ranked)"),
                            mo.ui.table(
                                reconstruction_rows[:30],
                                selection=None,
                            ),
                        ],
                        gap=1,
                    ),
                    mo.vstack(
                        [
                            mo.md("#### Top novel predictions (full model)"),
                            mo.ui.table(top_rows, selection=None),
                        ],
                        gap=1,
                    ),
                ],
                gap=2,
            )
    abl_output
    return


if __name__ == "__main__":
    app.run()
