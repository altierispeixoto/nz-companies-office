"""Device selection utilities for torch."""

from __future__ import annotations

import torch


def get_device() -> torch.device:
    """Select the best available device for PyTorch.

    Returns:
        CUDA device if available, else MPS (Apple Silicon) if available,
        else CPU.

    """
    return torch.device(
        "cuda" if torch.cuda.is_available() else "mps" if torch.backends.mps.is_available() else "cpu",
    )
