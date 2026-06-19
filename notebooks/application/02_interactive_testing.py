# ---
# marimo-version: 0.23.9
# license: Apache-2.0
# ---

import marimo

__generated_with = "0.23.9"
app = marimo.App(width="full")


@app.cell
def _():
    import pathlib

    import marimo as mo
    import torch
    from torch.nn import functional as F  # noqa: N812

    from nz_companies_office.models.link_predictor import LinkPredictor
    from nz_companies_office.utils.device import get_device

    device = get_device()
    return F, LinkPredictor, device, mo, pathlib, torch


@app.cell
def _():
    return


@app.cell
def _(mo, pathlib, torch):
    pipeline_path = pathlib.Path("data/processed/pipeline_checkpoint/pipeline.pt")
    if pipeline_path.exists():
        _ckpt = torch.load(pipeline_path, map_location="cpu", weights_only=False)
        data = _ckpt["data"]
        n_company_feats = _ckpt["n_company_feats"]
        n_director_feats = _ckpt["n_director_feats"]
        n_shareholder_feats = _ckpt["n_shareholder_feats"]
        n_industry_feats = _ckpt.get("n_industry_feats", 0)
    else:
        mo.output.append(mo.md("\u26a0\ufe0f **No pipeline checkpoint**. Run the main training notebook first."))
        data = None
        n_company_feats = None
        n_director_feats = None
        n_shareholder_feats = None
        n_industry_feats = 0
    return data, n_company_feats, n_director_feats, n_shareholder_feats, n_industry_feats


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

        with torch.no_grad():
            _x_dict = model.encode(data)
            z_share = _x_dict["shareholder"]
            z_comp = _x_dict["company"]

        n_comp = z_comp.shape[0]
        n_share = z_share.shape[0]

        try:
            comp_names = list(data["company"].names)
        except (AttributeError, KeyError):
            comp_names = [f"Company #{i}" for i in range(n_comp)]
        try:
            share_names = list(data["shareholder"].names)
        except (AttributeError, KeyError):
            share_names = [f"Shareholder #{i}" for i in range(n_share)]
        comp_name_to_idx = {name: i for i, name in enumerate(comp_names)}
    else:
        if data is None:
            mo.output.append(mo.md("\u26a0\ufe0f **Pipeline checkpoint not loaded**."))
        else:
            mo.output.append(
                mo.md("\u26a0\ufe0f **No model checkpoint found** at `data/processed/model_checkpoint.pt`.")
            )
        z_share = None
        z_comp = None
        comp_names = None
        share_names = None
        comp_name_to_idx = None
    return comp_name_to_idx, comp_names, share_names, z_comp, z_share


@app.cell
def _(mo):
    search_input = mo.ui.text(label="Search companies", placeholder="Type name to filter...")
    search_input
    return (search_input,)


@app.cell
def _(comp_names, mo, search_input):
    if comp_names is None:
        company_selector = mo.md("\u26a0\ufe0f No companies loaded — run the training pipeline first.")
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
    if z_share is not None and z_comp is not None and hasattr(company_selector, "value"):
        company = company_selector.value
        comp_idx = comp_name_to_idx[company]

        share_edge_index = data["shareholder", "share", "company"].edge_index
        existing_mask = share_edge_index[1] == comp_idx
        existing_ids = share_edge_index[0][existing_mask]
        existing_rows = [{"Shareholder": share_names[i.item()]} for i in existing_ids]

        logits = z_share @ z_comp[comp_idx]
        probs = torch.sigmoid(logits)
        _top_k = 30
        _top_indices = probs.argsort(descending=True)[:_top_k]

        _avg_sim = []
        _best_existing = []
        _coinvest = []
        if existing_ids.numel() > 0:
            existing_all = share_edge_index[1][torch.isin(share_edge_index[0], existing_ids)]
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

                recom_comps = set(share_edge_index[1][share_edge_index[0] == s].tolist())
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
                    ]
                ),
                mo.vstack(
                    [
                        mo.md("### Top predicted shareholders"),
                        mo.ui.table(_pred_rows, selection=None),
                    ]
                ),
            ],
            gap=2,
        )
    else:
        output = None
    output
    return


if __name__ == "__main__":
    app.run()
