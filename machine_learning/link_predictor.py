"""Heterogeneous GNN model for shareholder link prediction."""

from __future__ import annotations

import torch
import torch.nn.functional as F  # noqa: N812
from torch import nn
from torch_geometric.nn import HeteroConv
from torch_geometric.nn import SAGEConv


class HeteroEncoder(nn.Module):
    """Two-layer GraphSAGE encoder with separate message functions per edge type.

    Produces node embeddings for director, company, shareholder, and industry
    nodes by passing messages along DIRECTS, HOLDS_SHARES_IN, and HAS_INDUSTRY
    edge types.
    """

    def __init__(
        self,
        dir_feats: int,
        comp_feats: int,
        share_feats: int,
        ind_feats: int = 0,
        hidden_dim: int = 32,
        out_dim: int = 16,
    ) -> None:
        """Initialize encoder with two HeteroConv layers."""
        super().__init__()
        base_conv1: dict = {
            ("director", "directs", "company"): SAGEConv((dir_feats, comp_feats), hidden_dim),
            ("company", "rev_directs", "director"): SAGEConv((comp_feats, dir_feats), hidden_dim),
            ("shareholder", "share", "company"): SAGEConv((share_feats, comp_feats), hidden_dim),
            ("company", "rev_share", "shareholder"): SAGEConv((comp_feats, share_feats), hidden_dim),
        }
        base_conv2: dict = {
            ("director", "directs", "company"): SAGEConv((hidden_dim, hidden_dim), out_dim),
            ("company", "rev_directs", "director"): SAGEConv((hidden_dim, hidden_dim), out_dim),
            ("shareholder", "share", "company"): SAGEConv((hidden_dim, hidden_dim), out_dim),
            ("company", "rev_share", "shareholder"): SAGEConv((hidden_dim, hidden_dim), out_dim),
        }

        if ind_feats > 0:
            base_conv1[("company", "has_industry", "industry")] = SAGEConv(
                (comp_feats, ind_feats),
                hidden_dim,
            )
            base_conv1[("industry", "rev_has_industry", "company")] = SAGEConv(
                (ind_feats, comp_feats),
                hidden_dim,
            )
            base_conv2[("company", "has_industry", "industry")] = SAGEConv(
                (hidden_dim, hidden_dim),
                out_dim,
            )
            base_conv2[("industry", "rev_has_industry", "company")] = SAGEConv(
                (hidden_dim, hidden_dim),
                out_dim,
            )

        self.conv1 = HeteroConv(base_conv1, aggr="mean")
        self.conv2 = HeteroConv(base_conv2, aggr="mean")

    def forward(self, x_dict, edge_index_dict):  # noqa: ANN001, ANN201
        """Run two message-passing rounds with ReLU between them.

        Args:
            x_dict: Dictionary mapping node type -> feature tensor.
            edge_index_dict: Dictionary mapping edge type -> edge_index.

        Returns:
            Dictionary mapping node type -> output embedding tensor.

        """
        x_dict = self.conv1(x_dict, edge_index_dict)
        x_dict = {k: F.relu(v) for k, v in x_dict.items()}
        return self.conv2(x_dict, edge_index_dict)


class Decoder(nn.Module):
    """Dot-product decoder for bipartite link prediction.

    Score = sum(z_src * z_dst) across embedding dimensions for each edge.
    """

    def forward(
        self,
        z_dir: torch.Tensor,
        z_comp: torch.Tensor,
        edge_index: torch.LongTensor,
    ) -> torch.Tensor:
        """Compute dot-product scores for given edges.

        Args:
            z_dir: Source node embeddings (shareholder or director).
            z_comp: Target node embeddings (company).
            edge_index: 2xE tensor of [src, dst] pairs.

        Returns:
            Score for each edge (un-normalized logit).

        """
        return (z_dir[edge_index[0]] * z_comp[edge_index[1]]).sum(dim=1)


class LinkPredictor(nn.Module):
    """Full link-prediction model: heterogeneous encoder + dot-product decoder."""

    def __init__(
        self,
        dir_feats: int,
        comp_feats: int,
        share_feats: int,
        ind_feats: int = 0,
        hidden_dim: int = 32,
        out_dim: int = 16,
    ) -> None:
        """Initialize the predictor with encoder and decoder."""
        super().__init__()
        self.encoder = HeteroEncoder(dir_feats, comp_feats, share_feats, ind_feats, hidden_dim, out_dim)
        self.decoder = Decoder()

    def encode(self, data):  # noqa: ANN001, ANN201
        """Encode all nodes from a HeteroData object.

        Args:
            data: HeteroData graph object.

        Returns:
            Dictionary of node type -> embedding tensor.

        """
        _device = next(self.parameters()).device
        data = data.to(_device)
        return self.encoder(data.x_dict, data.edge_index_dict)
