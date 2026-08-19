import flwr as fl
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Optional real-time dashboard integration
try:
    from utils.real_time_logger import RealTimeLogger
    _rt_logger = None  # Disabled locally
except Exception:
    _rt_logger = None

import yaml
import torch
import numpy as np
from collections import OrderedDict
from models.factory import get_model
from federated.strategies import get_strategy
from utils.experiment_manager import set_seed
from typing import Dict, Optional


def _make_fit_config_fn(config, country_name):
    """Create a fit config function that passes strategy-specific params to clients."""
    strategy_name = config['federated'].get('strategy', 'fedavg').lower()
    proximal_mu = config['federated'].get('proximal_mu', 0.1)

    def fit_config(server_round: int):
        fit_cfg = {"server_round": server_round}
        if strategy_name == 'fedprox':
            fit_cfg["proximal_mu"] = proximal_mu
        return fit_cfg
    return fit_config


def start_country_server(country_name, port, config):
    print(f"[{country_name}] Starting Country Server on port {port}...")

    # Set seed for reproducibility
    seed = config.get('experiment', {}).get('seed', 42)
    set_seed(seed)

    strategy_name = config['federated'].get('strategy', 'fedavg').lower()
    num_clients = len(config['network']['countries'][country_name]['clients'])

    print(f"[{country_name}] Strategy: {strategy_name}, Clients: {num_clients}")

    # Use strategy factory
    strategy = get_strategy(
        strategy_name=strategy_name,
        config=config,
        save_label=country_name,
        num_clients=num_clients,
        on_fit_config_fn=_make_fit_config_fn(config, country_name),
    )

    # Run server
    hist = fl.server.start_server(
        server_address=f"0.0.0.0:{port}",
        config=fl.server.ServerConfig(num_rounds=config['federated']['num_rounds_country']),
        strategy=strategy,
    )

    print(f"[{country_name}] Training complete.")
    return hist

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Country Server")
    parser.add_argument("--country", type=str, required=True, help="Country name (e.g., country_A)")
    parser.add_argument("--port", type=int, required=True, help="Port to listen on")
    parser.add_argument("--config", type=str, default="config/physical_config.yaml")
    args = parser.parse_args()

    with open(args.config, 'r') as f:
        config = yaml.safe_load(f)

    start_country_server(args.country, args.port, config)
