"""HeteroData graph construction for the investor network."""

from __future__ import annotations

from typing import TYPE_CHECKING

from torch_geometric.data import HeteroData

if TYPE_CHECKING:
    import torch


def build_hetero_data(
    x_company: torch.Tensor,
    x_director: torch.Tensor,
    x_shareholder: torch.Tensor,
    n_company: int,
    n_director: int,
    n_shareholder: int,
    comp_names: list[str],
    dir_names: list[str],
    share_names: list[str],
    dir_edge_index: torch.LongTensor,
    share_edge_index: torch.LongTensor,
    device: torch.device,
    x_industry: torch.Tensor | None = None,
    n_industry: int = 0,
    ind_edge_index: torch.LongTensor | None = None,
) -> HeteroData:
    """Construct a HeteroData graph from pre-computed features and edges.

    Includes both forward and reverse edge types for bidirectional
    message passing. Moves the graph to the target device.

    Args:
        x_company: Company feature matrix (N_comp x feat_dim).
        x_director: Director feature matrix (N_dir x feat_dim).
        x_shareholder: Shareholder feature matrix (N_share x feat_dim).
        n_company: Number of company nodes.
        n_director: Number of director nodes.
        n_shareholder: Number of shareholder nodes.
        comp_names: Human-readable company names.
        dir_names: Human-readable director names.
        share_names: Human-readable shareholder names.
        dir_edge_index: 2xE director->company edge index.
        share_edge_index: 2xE shareholder->company edge index.
        device: Target torch device.
        x_industry: Industry feature matrix (N_ind x feat_dim) or None.
        n_industry: Number of industry nodes.
        ind_edge_index: 2xE company->industry edge index or None.

    Returns:
        Populated HeteroData object on the target device.

    """
    data = HeteroData()

    data["company"].x = x_company
    data["company"].num_nodes = n_company
    data["company"].names = comp_names

    data["director"].x = x_director
    data["director"].num_nodes = n_director
    data["director"].names = dir_names

    data["shareholder"].x = x_shareholder
    data["shareholder"].num_nodes = n_shareholder
    data["shareholder"].names = share_names

    data["director", "directs", "company"].edge_index = dir_edge_index
    data["company", "rev_directs", "director"].edge_index = dir_edge_index[[1, 0]]
    data["shareholder", "share", "company"].edge_index = share_edge_index
    data["company", "rev_share", "shareholder"].edge_index = share_edge_index[[1, 0]]

    if x_industry is not None and ind_edge_index is not None:
        data["industry"].x = x_industry
        data["industry"].num_nodes = n_industry
        data["company", "has_industry", "industry"].edge_index = ind_edge_index
        data["industry", "rev_has_industry", "company"].edge_index = ind_edge_index[[1, 0]]

    return data.to(device)
