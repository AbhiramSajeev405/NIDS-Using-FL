"""
Aggregation Strategy Factory for Federated Learning.

Maps config strings to Flower strategy implementations.
All strategies include model-saving behaviour via SaveModelMixin.
"""

import os
import numpy as np
import torch
from collections import OrderedDict
from typing import Dict, Optional

import flwr as fl
from flwr.common import Parameters, FitRes, Scalar, parameters_to_ndarrays, ndarrays_to_parameters
from flwr.server.client_proxy import ClientProxy
from flwr.server.strategy import FedAvg


# ---------------------------------------------------------------------------
# Save Model Mixin — shared model-saving logic
# ---------------------------------------------------------------------------
class SaveModelMixin:
    """Mixin that saves aggregated weights to disk after each round."""

    def _save_model(self, ndarrays, server_round, label="global"):
        """Persist aggregated weights to disk."""
        try:
            from models.factory import get_model
            device = torch.device("cpu")
            model_type = self.config.get('model', {}).get('type', self.config.get('model_type', 'mlp'))
            input_dim = self.config.get('model', {}).get('input_dim', self.config.get('input_dim', 78))
            num_classes = self.config.get('model', {}).get('num_classes', self.config.get('num_classes', 2))
            model = get_model(model_type, input_dim, num_classes).to(device)

            params_dict = zip(model.state_dict().keys(), ndarrays)
            state_dict = OrderedDict({k: torch.tensor(v) for k, v in params_dict})
            model.load_state_dict(state_dict, strict=True)

            _ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            models_dir = os.path.join(_ROOT, "models")
            os.makedirs(models_dir, exist_ok=True)

            # Get aggregation algorithm name for filename
            algo_name = self.__class__.__name__.lower().replace('_', '')

            # Save with format: {modeltype}_{algorithm}_model.pth
            save_path = os.path.join(models_dir, f"{model_type}_{algo_name}_model.pth")
            torch.save(model.state_dict(), save_path)
            print(f"[{label}] Round {server_round}: Saved aggregated weights to {save_path}")
        except Exception as e:
            print(f"[{label}] Warning: Could not save model: {e}")


# ---------------------------------------------------------------------------
# FedAvg with model saving
# ---------------------------------------------------------------------------
class SavedFedAvg(SaveModelMixin, FedAvg):
    """Standard FedAvg + auto-save after each aggregation round."""

    def __init__(self, config, save_label="global", *args, **kwargs):
        FedAvg.__init__(self, *args, **kwargs)
        self.config = config
        self.save_label = save_label

    def aggregate_fit(self, server_round, results, failures):
        aggregated_parameters, aggregated_metrics = super().aggregate_fit(
            server_round, results, failures
        )
        if aggregated_parameters is not None:
            ndarrays = parameters_to_ndarrays(aggregated_parameters)
            self._save_model(ndarrays, server_round, self.save_label)
        return aggregated_parameters, aggregated_metrics

    def aggregate_evaluate(self, server_round, results, failures):
        """Aggregate evaluation metrics using the custom aggregation function."""
        if not results:
            return None, {}
        
        # Build standard result payload expected by evaluate_metrics_aggregation_fn
        # results is a list of tuples: (ClientProxy, EvaluateRes)
        # We need a list of tuples: (num_examples, metrics)
        metrics_results = []
        for _, evaluate_res in results:
            metrics_results.append((evaluate_res.num_examples, evaluate_res.metrics))
            
        aggregated_loss, aggregated_metrics = super().aggregate_evaluate(
            server_round, results, failures
        )
        
        # Override with our custom detailed logger
        if hasattr(self, "evaluate_metrics_aggregation_fn") and self.evaluate_metrics_aggregation_fn:
            aggregated_metrics = self.evaluate_metrics_aggregation_fn(metrics_results)
            
        return aggregated_loss, aggregated_metrics


# ---------------------------------------------------------------------------
# FedMedian — coordinate-wise median (Byzantine-robust)
# ---------------------------------------------------------------------------
class FedMedian(SaveModelMixin, FedAvg):
    """Coordinate-wise median aggregation.

    Instead of averaging client parameters, takes the median at each
    coordinate. A single poisoned client cannot skew the result.
    Reference: Yin et al. 'Byzantine-Robust Distributed Learning' (ICML 2018)
    """

    def __init__(self, config, save_label="global", *args, **kwargs):
        FedAvg.__init__(self, *args, **kwargs)
        self.config = config
        self.save_label = save_label

    def aggregate_fit(self, server_round, results, failures):
        if not results:
            return None, {}

        # Extract ndarrays from each client
        all_weights = [parameters_to_ndarrays(res.parameters) for _, res in results]

        # Compute coordinate-wise median
        median_weights = [
            np.median(np.array([w[i] for w in all_weights]), axis=0)
            for i in range(len(all_weights[0]))
        ]

        aggregated_parameters = ndarrays_to_parameters(median_weights)
        self._save_model(median_weights, server_round, self.save_label)
        print(f"[{self.save_label}] Round {server_round}: FedMedian aggregation complete ({len(results)} clients)")

        return aggregated_parameters, {}


# ---------------------------------------------------------------------------
# Trimmed Mean — trim outliers then average
# ---------------------------------------------------------------------------
class TrimmedMean(SaveModelMixin, FedAvg):
    """Trimmed Mean aggregation.

    Sorts parameter values per coordinate and trims the top/bottom
    `trim_ratio` fraction before averaging. Robust to bounded adversaries.
    Reference: Yin et al. 'Byzantine-Robust Distributed Learning' (ICML 2018)
    """

    def __init__(self, config, save_label="global", trim_ratio=0.1, *args, **kwargs):
        FedAvg.__init__(self, *args, **kwargs)
        self.config = config
        self.save_label = save_label
        self.trim_ratio = trim_ratio

    def aggregate_fit(self, server_round, results, failures):
        if not results:
            return None, {}

        all_weights = [parameters_to_ndarrays(res.parameters) for _, res in results]
        n_clients = len(all_weights)
        trim_count = max(1, int(n_clients * self.trim_ratio))

        trimmed_weights = []
        for i in range(len(all_weights[0])):
            stacked = np.array([w[i] for w in all_weights])
            # Sort along client axis, trim top/bottom
            sorted_vals = np.sort(stacked, axis=0)
            # Trim trim_count from each end
            if n_clients > 2 * trim_count:
                trimmed = sorted_vals[trim_count:-trim_count]
            else:
                trimmed = sorted_vals  # Not enough clients to trim
            trimmed_weights.append(np.mean(trimmed, axis=0))

        aggregated_parameters = ndarrays_to_parameters(trimmed_weights)
        self._save_model(trimmed_weights, server_round, self.save_label)
        print(f"[{self.save_label}] Round {server_round}: TrimmedMean (trim={self.trim_ratio}) done ({len(results)} clients)")

        return aggregated_parameters, {}


# ---------------------------------------------------------------------------
# Krum / Multi-Krum — distance-based selection
# ---------------------------------------------------------------------------
class Krum(SaveModelMixin, FedAvg):
    """Krum aggregation.

    Selects the client update whose sum of distances to its nearest
    (n - f - 2) neighbors is minimal. Multi-Krum averages the top-m
    selected updates.
    Reference: Blanchard et al. 'Machine Learning with Adversaries' (NeurIPS 2017)
    """

    def __init__(self, config, save_label="global", num_malicious=1, multi_krum_k=1, *args, **kwargs):
        FedAvg.__init__(self, *args, **kwargs)
        self.config = config
        self.save_label = save_label
        self.num_malicious = num_malicious
        self.multi_krum_k = multi_krum_k  # 1 = Krum, >1 = Multi-Krum

    def _flatten(self, weights):
        """Flatten all parameter arrays into a single vector."""
        return np.concatenate([w.flatten() for w in weights])

    def aggregate_fit(self, server_round, results, failures):
        if not results:
            return None, {}

        all_weights = [parameters_to_ndarrays(res.parameters) for _, res in results]
        n = len(all_weights)
        f = self.num_malicious

        # Flatten each client's weights into a vector
        flat_vectors = [self._flatten(w) for w in all_weights]

        # Compute pairwise squared distances
        distances = np.zeros((n, n))
        for i in range(n):
            for j in range(i + 1, n):
                dist = np.sum((flat_vectors[i] - flat_vectors[j]) ** 2)
                distances[i][j] = dist
                distances[j][i] = dist

        # For each client, sum distances to closest (n - f - 2) neighbours
        num_closest = max(1, n - f - 2)
        scores = []
        for i in range(n):
            sorted_dists = np.sort(distances[i])
            # sorted_dists[0] is 0 (distance to self), skip it
            score = np.sum(sorted_dists[1:num_closest + 1])
            scores.append(score)

        # Select top-k (Multi-Krum) or top-1 (Krum)
        k = min(self.multi_krum_k, n)
        selected_indices = np.argsort(scores)[:k]

        # Average the selected updates
        krum_weights = []
        for i in range(len(all_weights[0])):
            stacked = np.array([all_weights[idx][i] for idx in selected_indices])
            krum_weights.append(np.mean(stacked, axis=0))

        aggregated_parameters = ndarrays_to_parameters(krum_weights)
        self._save_model(krum_weights, server_round, self.save_label)

        selected_str = ', '.join([str(i) for i in selected_indices])
        print(f"[{self.save_label}] Round {server_round}: Krum selected clients [{selected_str}] ({len(results)} total)")

        return aggregated_parameters, {}


# ---------------------------------------------------------------------------
# FedNova — normalized averaging by local steps
# ---------------------------------------------------------------------------
class FedNova(SaveModelMixin, FedAvg):
    """FedNova: Normalized Averaging.

    Normalizes each client's update by the number of local steps taken
    before averaging. Handles heterogeneous local training.
    Reference: Wang et al. 'Tackling the Objective Inconsistency Problem' (NeurIPS 2020)

    Clients must send 'num_steps' in their fit metrics for this to work.
    Falls back to FedAvg behaviour if num_steps is not provided.
    """

    def __init__(self, config, save_label="global", *args, **kwargs):
        FedAvg.__init__(self, *args, **kwargs)
        self.config = config
        self.save_label = save_label

    def aggregate_fit(self, server_round, results, failures):
        if not results:
            return None, {}

        all_weights = []
        all_steps = []
        all_samples = []

        for _, res in results:
            weights = parameters_to_ndarrays(res.parameters)
            all_weights.append(weights)
            # Get num_steps from client metrics (default=1 if not sent)
            num_steps = res.metrics.get("num_steps", 1)
            all_steps.append(num_steps)
            all_samples.append(res.num_examples)

        # Compute normalized weights: tau_eff / tau_i * (p_i / P)
        total_samples = sum(all_samples)
        tau_eff = sum(all_steps) / len(all_steps)  # Average steps

        nova_weights = []
        for i in range(len(all_weights[0])):
            weighted_sum = np.zeros_like(all_weights[0][i], dtype=np.float64)
            for j, w in enumerate(all_weights):
                # Normalize by steps taken and weight by samples
                coeff = (tau_eff / max(all_steps[j], 1)) * (all_samples[j] / max(total_samples, 1))
                weighted_sum += coeff * w[i].astype(np.float64)
            nova_weights.append(weighted_sum.astype(all_weights[0][i].dtype))

        aggregated_parameters = ndarrays_to_parameters(nova_weights)
        self._save_model(nova_weights, server_round, self.save_label)
        print(f"[{self.save_label}] Round {server_round}: FedNova (steps={all_steps}) done")

        return aggregated_parameters, {}


# ---------------------------------------------------------------------------
# Strategy Factory
# ---------------------------------------------------------------------------
def get_strategy(strategy_name, config, save_label="global", num_clients=1, on_fit_config_fn=None):
    """Factory function to create a Flower strategy from config.

    Args:
        strategy_name: One of 'fedavg', 'fedprox', 'fedmedian', 'trimmed_mean', 'krum', 'fednova'
        config: Full experiment config dict
        save_label: Label for saved model files (e.g., 'global' or 'country_A')
        num_clients: Expected number of clients
        on_fit_config_fn: Function to generate per-round fit config

    Returns:
        A Flower Strategy instance
    """
    name = strategy_name.lower()
    fed_config = config.get('federated', {})

    common_kwargs = dict(
        fraction_fit=1.0,
        fraction_evaluate=1.0,
        min_fit_clients=num_clients,
        min_evaluate_clients=num_clients,
        min_available_clients=num_clients,
        on_fit_config_fn=on_fit_config_fn,
    )

    if name in ('fedavg', 'fedprox'):
        # FedProx uses the same server-side aggregation as FedAvg.
        # The proximal term is applied client-side.
        return SavedFedAvg(config=config, save_label=save_label, **common_kwargs)

    elif name == 'fedmedian':
        return FedMedian(config=config, save_label=save_label, **common_kwargs)

    elif name == 'trimmed_mean':
        trim_ratio = fed_config.get('trim_ratio', 0.1)
        return TrimmedMean(config=config, save_label=save_label, trim_ratio=trim_ratio, **common_kwargs)

    elif name == 'krum':
        num_malicious = fed_config.get('krum_num_malicious', 1)
        multi_k = fed_config.get('krum_multi_k', 1)
        return Krum(config=config, save_label=save_label, num_malicious=num_malicious, multi_krum_k=multi_k, **common_kwargs)

    elif name == 'fednova':
        return FedNova(config=config, save_label=save_label, **common_kwargs)

    else:
        available = list_strategies()
        raise ValueError(f"Strategy '{strategy_name}' not recognized. Options: {available}")


def list_strategies():
    """Returns list of all available strategy names."""
    return ['fedavg', 'fedprox', 'fedmedian', 'trimmed_mean', 'krum', 'fednova']
