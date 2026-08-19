"""
Client Selection Strategies for Federated Learning.

Controls which clients participate in each FL round.
Integrated into strategy via on_fit_config_fn and configure_fit.

Strategies:
  - all: All clients participate (default)
  - random: Random K of N clients per round
  - power_of_choice: Prioritize clients with highest local loss

Reference: Cho et al. 'Client Selection in Federated Learning' (ICLR 2022)
"""

import numpy as np


class ClientSelector:
    """Select which clients participate in each FL round."""

    def __init__(self, strategy='all', total_clients=9, fraction=1.0,
                 num_malicious=0, seed=42):
        """
        Args:
            strategy: 'all', 'random', or 'power_of_choice'
            total_clients: Total number of available clients
            fraction: Fraction of clients to select per round (for random/poc)
            num_malicious: Known malicious clients (for Krum-aware selection)
            seed: Random seed
        """
        self.strategy = strategy.lower()
        self.total_clients = total_clients
        self.fraction = fraction
        self.k = max(1, int(total_clients * fraction))
        self.rng = np.random.RandomState(seed)
        self.client_losses = {}  # Track per-client losses for power_of_choice

    def select(self, available_clients, round_num=0):
        """Select clients for this round.

        Args:
            available_clients: List of client identifiers
            round_num: Current FL round number

        Returns:
            List of selected client identifiers
        """
        n = len(available_clients)

        if self.strategy == 'all' or self.k >= n:
            return list(available_clients)

        elif self.strategy == 'random':
            indices = self.rng.choice(n, size=min(self.k, n), replace=False)
            selected = [available_clients[i] for i in indices]
            return selected

        elif self.strategy == 'power_of_choice':
            return self._power_of_choice(available_clients)

        else:
            raise ValueError(f"Unknown selection strategy: {self.strategy}")

    def _power_of_choice(self, available_clients):
        """Select clients with highest reported local loss.

        Prioritizes 'struggling' clients, which helps with
        convergence under Non-IID data.

        If no loss data is available, falls back to random selection.
        """
        if not self.client_losses:
            # No loss data yet, fall back to random
            indices = self.rng.choice(len(available_clients), size=min(self.k, len(available_clients)), replace=False)
            return [available_clients[i] for i in indices]

        # Rank clients by their latest loss (highest = most struggling)
        ranked = sorted(
            available_clients,
            key=lambda c: self.client_losses.get(c, 0),
            reverse=True
        )
        return ranked[:self.k]

    def update_loss(self, client_id, loss):
        """Update the tracked loss for a client.

        Called after each round with the client's training loss.
        """
        self.client_losses[client_id] = loss

    def summary(self, round_num, selected):
        """Print selection summary."""
        print(f"[ClientSelector] Round {round_num}: {self.strategy} selected "
              f"{len(selected)}/{self.total_clients} clients: {selected}")


def get_client_selector(config):
    """Create a ClientSelector from config.

    Reads from config['federated']['client_selection'] and
    config['federated']['client_fraction'].

    Args:
        config: Full experiment config dict

    Returns:
        ClientSelector instance
    """
    fed_cfg = config.get('federated', {})
    strategy = fed_cfg.get('client_selection', 'all')
    fraction = fed_cfg.get('client_fraction', 1.0)
    seed = config.get('experiment', {}).get('seed', 42)

    # Count total clients
    total = 0
    countries = config.get('network', {}).get('countries', {})
    for country in countries.values():
        total += len(country.get('clients', []))
    if total == 0:
        total = 9  # Default fallback

    return ClientSelector(
        strategy=strategy,
        total_clients=total,
        fraction=fraction,
        seed=seed,
    )
