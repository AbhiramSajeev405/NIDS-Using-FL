"""
Contribution Evaluation for Federated Learning.

Scores each client's update by computing the cosine similarity between
each client's update and the mean update. Clients with similarity below
a threshold are flagged and rejected.

This is a lightweight server-side defense against model poisoning attacks.
"""

import numpy as np


def _flatten(arrays):
    """Flatten a list of numpy arrays into a single vector."""
    return np.concatenate([a.flatten() for a in arrays])


def cosine_similarity(a, b):
    """Compute cosine similarity between two vectors."""
    norm_a = np.linalg.norm(a)
    norm_b = np.linalg.norm(b)
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return np.dot(a, b) / (norm_a * norm_b)


def evaluate_contributions(client_updates, threshold=0.5):
    """Score and filter client updates based on cosine similarity.

    Args:
        client_updates: List of (client_id, parameters) tuples
            where parameters is a list of numpy arrays
        threshold: Minimum cosine similarity to keep a client's update

    Returns:
        Filtered list of (client_id, parameters) tuples
    """
    if len(client_updates) <= 1:
        return client_updates

    # Flatten all updates
    flat_updates = [(cid, _flatten(params)) for cid, params in client_updates]

    # Compute mean update
    mean_update = np.mean([flat for _, flat in flat_updates], axis=0)

    # Score each client
    accepted = []
    for cid, flat in flat_updates:
        sim = cosine_similarity(flat, mean_update)
        if sim >= threshold:
            # Find the original (non-flattened) params for this client
            original = next(params for c, params in client_updates if c == cid)
            accepted.append((cid, original))
            print(f"[ContribEval] {cid}: similarity={sim:.4f} — ACCEPTED")
        else:
            print(f"[ContribEval] {cid}: similarity={sim:.4f} — REJECTED (below {threshold})")

    if not accepted:
        print("[ContribEval] Warning: All clients rejected! Keeping all to avoid deadlock.")
        return client_updates

    return accepted
