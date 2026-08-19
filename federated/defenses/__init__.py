"""
Defense mechanisms for Federated Learning.

Provides client-side and server-side defenses that can be toggled via config.
All defenses are applied as pre/post-processing steps on model parameters.
"""

from federated.defenses.differential_privacy import apply_dp_noise
from federated.defenses.gradient_clipping import clip_update
from federated.defenses.contribution_eval import evaluate_contributions


def apply_client_defenses(parameters, global_parameters, config):
    """Apply client-side defenses to parameters before sending to server.

    Args:
        parameters: List of numpy arrays (client model weights)
        global_parameters: List of numpy arrays (global model weights before training)
        config: Full experiment config dict

    Returns:
        List of numpy arrays (defended parameters)
    """
    defense_cfg = config.get('defense', {})

    # 1. Gradient Clipping: clip the update (delta) norm
    if defense_cfg.get('gradient_clipping', False):
        clip_norm = defense_cfg.get('clip_norm', 1.0)
        parameters = clip_update(parameters, global_parameters, clip_norm)

    # 2. Differential Privacy: add calibrated noise
    if defense_cfg.get('differential_privacy', False):
        epsilon = defense_cfg.get('dp_epsilon', 1.0)
        delta = defense_cfg.get('dp_delta', 1e-5)
        clip_norm = defense_cfg.get('clip_norm', 1.0)
        parameters = apply_dp_noise(parameters, epsilon, delta, clip_norm)

    return parameters


def apply_server_defenses(all_parameters, config):
    """Apply server-side defenses to filter/score client updates.

    Args:
        all_parameters: List of (client_id, parameters) tuples
        config: Full experiment config dict

    Returns:
        Filtered list of (client_id, parameters) tuples
    """
    defense_cfg = config.get('defense', {})

    # Contribution Evaluation: reject outlier updates
    if defense_cfg.get('contribution_eval', False):
        threshold = defense_cfg.get('contribution_threshold', 0.5)
        all_parameters = evaluate_contributions(all_parameters, threshold)

    return all_parameters
