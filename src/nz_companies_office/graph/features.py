"""Node feature construction for the heterogeneous investor graph."""

from __future__ import annotations

import torch
import torch.nn.functional as F  # noqa: N812
from torch_geometric.utils import degree


def build_node_features(
    comp_statuses: list[str],
    comp_types: list[str],
    dir_edge_index: torch.LongTensor,
    n_director: int,
    n_company: int,
    n_shareholder: int,
    share_edge_index: torch.LongTensor,
) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor, int, int, int]:
    """Build feature tensors for company, director, and shareholder nodes.

    Company features: status one-hot + type one-hot + normalized director-degree.
    Director features: normalized degree + small random noise.
    Shareholder features: normalized degree + small random noise.

    Args:
        comp_statuses: Company status strings (e.g. "Registered", "Removed").
        comp_types: Company entity type strings.
        dir_edge_index: 2xE tensor of director->company edges.
        n_director: Number of director nodes.
        n_company: Number of company nodes.
        n_shareholder: Number of shareholder nodes.
        share_edge_index: 2xE tensor of shareholder->company edges.

    Returns:
        Tuple of (x_company, x_director, x_shareholder,
                  n_company_feats, n_director_feats, n_shareholder_feats).

    """
    num_statuses = len(set(comp_statuses))
    num_types = len(set(comp_types))

    status_map = {s: i for i, s in enumerate(set(comp_statuses))}
    type_map = {t: i for i, t in enumerate(set(comp_types))}

    x_status = F.one_hot(torch.tensor([status_map[s] for s in comp_statuses]), num_classes=num_statuses).float()
    x_type = F.one_hot(torch.tensor([type_map[t] for t in comp_types]), num_classes=num_types).float()

    dir_deg = degree(dir_edge_index[0], num_nodes=n_director).float().unsqueeze(1)
    comp_deg = degree(dir_edge_index[1], num_nodes=n_company).float().unsqueeze(1)

    x_company = torch.cat(
        [
            x_status,
            x_type,
            comp_deg / (comp_deg.max() + 1e-8),
        ],
        dim=1,
    )

    x_director = torch.cat(
        [
            dir_deg / (dir_deg.max() + 1e-8),
            torch.randn(n_director, num_statuses + num_types) * 0.1,
        ],
        dim=1,
    )

    share_deg = (
        degree(share_edge_index[0], num_nodes=n_shareholder).float().unsqueeze(1)
        if share_edge_index.shape[1] > 0
        else torch.zeros(n_shareholder, 1)
    )
    x_shareholder = torch.cat(
        [
            share_deg / (share_deg.max() + 1e-8),
            torch.randn(n_shareholder, num_statuses + num_types) * 0.1,
        ],
        dim=1,
    )

    n_company_feats = x_company.shape[1]
    n_director_feats = x_director.shape[1]
    n_shareholder_feats = x_shareholder.shape[1]

    return x_company, x_director, x_shareholder, n_company_feats, n_director_feats, n_shareholder_feats
