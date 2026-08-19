"""
Gradient Clipping for Federated Learning.

Clips the L2 norm of the model update (difference between trained weights
and global weights) to a maximum value. Limits the influence of any
single client on the global model.

This is a standard defense that is also required as a prerequisite for
Differential Privacy (DP) — the sensitivity of the mechanism depends on
the clipping norm.
"""

import numpy as np


def clip_update(local_params, global_params, clip_norm=1.0):
    """Clip the L2 norm of the update (local - global) to clip_norm.

    If the update norm exceeds clip_norm, the update is scaled down
    proportionally, and the clipped parameters are returned.

    Args:
        local_params: List of numpy arrays (trained local weights)
        global_params: List of numpy arrays (global weights before training)
        clip_norm: Maximum allowed L2 norm of the update

    Returns:
        List of numpy arrays (clipped local weights)
    """
    # Compute the update (delta = local - global)
    deltas = [lp - gp for lp, gp in zip(local_params, global_params)]

    # Compute L2 norm of the full delta vector
    total_norm = np.sqrt(sum(np.sum(d ** 2) for d in deltas))

    if total_norm > clip_norm:
        # Scale down the update
        scale = clip_norm / total_norm
        clipped_params = [gp + scale * d for gp, d in zip(global_params, deltas)]
        return clipped_params
    else:
        return local_params
