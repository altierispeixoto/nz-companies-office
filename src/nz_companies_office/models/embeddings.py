"""Industry description embedding using sentence-transformers with disk caching."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import torch

_CACHE_DIR = Path("data/processed/industry_embeddings")


def embed_industry_descriptions(
    descriptions: list[str],
    model_name: str = "all-MiniLM-L6-v2",
) -> torch.Tensor:
    """Encode industry descriptions into dense vectors using sentence-transformers.

    Runs on CPU to leave GPU memory available for GNN training.  Results are
    cached to disk so the model is only loaded once per unique set of descriptions.

    Args:
        descriptions: Human-readable industry description strings.  Any ``None``
            entries are treated as empty strings.
        model_name: Sentence-transformer model ID.

    Returns:
        ``(n_industries, embedding_dim)`` float tensor.

    """
    if not descriptions:
        return torch.empty(0, 0)

    # Guard against None entries (e.g. from Neo4j null descriptions).
    descriptions = [d or "" for d in descriptions]

    _CACHE_DIR.mkdir(parents=True, exist_ok=True)

    # Derive a stable cache key from the descriptions and model name.
    content = json.dumps(list(descriptions), sort_keys=True) + model_name
    cache_key = hashlib.sha256(content.encode()).hexdigest()[:16]
    cache_path = _CACHE_DIR / f"{cache_key}.pt"

    if cache_path.exists():
        return torch.load(cache_path, map_location="cpu", weights_only=True)

    from sentence_transformers import SentenceTransformer  # noqa: PLC0415

    model = SentenceTransformer(model_name, device="cpu")
    embeddings = model.encode(
        descriptions,
        convert_to_tensor=True,
        show_progress_bar=False,
    )
    torch.save(embeddings, cache_path)
    return embeddings
