"""
Differential Privacy for Federated Learning.

Adds calibrated Gaussian noise to model parameters before sending to the
server. The noise is calibrated using the (epsilon, delta)-DP guarantee
with the Gaussian mechanism.

Reference: Abadi et al. 'Deep Learning with Differential Privacy' (CCS 2016)
"""

import numpy as np


def _compute_noise_scale(epsilon, delta, sensitivity):
    """Compute Gaussian noise standard deviation for (eps, delta)-DP.

    Uses the analytic Gaussian mechanism bound:
        sigma >= sensitivity * sqrt(2 * ln(1.25 / delta)) / epsilon
    """
    return sensitivity * np.sqrt(2.0 * np.log(1.25 / delta)) / epsilon


def apply_dp_noise(parameters, epsilon=1.0, delta=1e-5, clip_norm=1.0):
    """Add Gaussian noise to each parameter array for DP.

    Args:
        parameters: List of numpy arrays (model weights)
        epsilon: Privacy budget (lower = more private, noisier)
        delta: Probability of privacy breach
        clip_norm: L2 sensitivity bound (should match gradient clipping norm)

    Returns:
        List of numpy arrays with added noise
    """
    if epsilon <= 0:
        raise ValueError(f"epsilon must be > 0, got {epsilon}")
    if delta <= 0 or delta >= 1:
        raise ValueError(f"delta must be in (0, 1), got {delta}")

    sigma = _compute_noise_scale(epsilon, delta, clip_norm)

    noisy_params = []
    for param in parameters:
        noise = np.random.normal(loc=0.0, scale=sigma, size=param.shape).astype(param.dtype)
        noisy_params.append(param + noise)

    return noisy_params
