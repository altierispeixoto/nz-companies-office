"""Edge splitting and negative sampling for link prediction."""

from __future__ import annotations

import torch
from torch_geometric.utils import negative_sampling


def split_share_edges(
    edge_index: torch.LongTensor,
    train_ratio: float = 0.7,
    val_ratio: float = 0.15,
) -> tuple[torch.LongTensor, torch.LongTensor, torch.LongTensor]:
    """Randomly split shareholder-company edges into train/val/test sets.

    Args:
        edge_index: 2xE shareholder->company edge index.
        train_ratio: Proportion of edges for training.
        val_ratio: Proportion of edges for validation (test gets remainder).

    Returns:
        Tuple of (train_pos, val_pos, test_pos) edge indices.

    """
    n_total = edge_index.shape[1]
    n_train = int(n_total * train_ratio)
    n_val = int(n_total * val_ratio)

    perm = torch.randperm(n_total)
    train_idx = perm[:n_train]
    val_idx = perm[n_train : n_train + n_val]
    test_idx = perm[n_train + n_val :]

    train_pos = edge_index[:, train_idx]
    val_pos = edge_index[:, val_idx]
    test_pos = edge_index[:, test_idx]

    return train_pos, val_pos, test_pos


def sample_negative_edges(
    train_pos: torch.LongTensor,
    val_pos: torch.LongTensor,
    test_pos: torch.LongTensor,
    n_shareholder: int,
    n_company: int,
) -> tuple[torch.LongTensor, torch.LongTensor]:
    """Generate negative (non-existent) edges for validation and test.

    Validation negatives are sampled avoiding train positives.
    Test negatives are sampled avoiding both train and validation positives.

    Args:
        train_pos: Training positive edge index.
        val_pos: Validation positive edge index.
        test_pos: Test positive edge index.
        n_shareholder: Number of shareholder nodes.
        n_company: Number of company nodes.

    Returns:
        Tuple of (val_neg, test_neg) edge indices.

    """
    val_neg = negative_sampling(
        train_pos,
        num_nodes=(n_shareholder, n_company),
        num_neg_samples=val_pos.shape[1],
    )
    test_neg = negative_sampling(
        torch.cat([train_pos, val_pos], dim=1),
        num_nodes=(n_shareholder, n_company),
        num_neg_samples=test_pos.shape[1],
    )
    return val_neg, test_neg
