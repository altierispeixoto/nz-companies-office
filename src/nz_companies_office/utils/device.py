"""Device selection utilities for torch."""

from __future__ import annotations

import warnings

import torch


def get_device(min_free_mib: int = 512) -> torch.device:
    """Select the best available device with sufficient free memory.

    Falls back to CPU when CUDA is available but has less than
    ``min_free_mib`` of free memory — this prevents spurious OOM errors
    from stale GPU processes holding memory.

    Args:
        min_free_mib: Minimum free GPU memory required (MiB).

    Returns:
        CUDA device if available with enough free memory, else MPS (Apple
        Silicon) if available, else CPU.

    """
    if not torch.cuda.is_available():
        return torch.device("mps" if torch.backends.mps.is_available() else "cpu")

    free_mib, _total = torch.cuda.mem_get_info(0)
    free_mib //= 1024 * 1024
    if free_mib >= min_free_mib:
        return torch.device("cuda")

    warnings.warn(
        f"CUDA available but only {free_mib:,} MiB free (need {min_free_mib:,}); falling back to CPU",
        stacklevel=1,
    )
    return torch.device("cpu")
