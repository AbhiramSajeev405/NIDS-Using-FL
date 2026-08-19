import flwr as fl
import sys
import os
import logging
from datetime import datetime
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Optional real-time dashboard integration
try:
    from utils.real_time_logger import RealTimeLogger
    _rt_logger = RealTimeLogger()
except Exception:
    _rt_logger = None

# Set up file logging
log_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "logs")
os.makedirs(log_dir, exist_ok=True)
timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
log_file = os.path.join(log_dir, f"server_{timestamp}.log")

# Configure logging - capture everything including flwr library logs
logging.basicConfig(
    level=logging.INFO,
    format='%(message)s',
    handlers=[
        logging.FileHandler(log_file, encoding='utf-8'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

# Also configure flwr library logging
flwr_logger = logging.getLogger('flwr')
flwr_logger.setLevel(logging.INFO)

import yaml
import torch
import torch.nn.functional as F
import numpy as np
from collections import OrderedDict
from models.factory import get_model
from federated.strategies import get_strategy
from utils.comm_tracker import CommTracker
from utils.experiment_manager import set_seed
from typing import Dict, Optional


def _make_fit_config_fn(config):
    """Create a fit config function that passes strategy-specific params to clients."""
    strategy_name = config.get('federated', {}).get('strategy', 'fedavg').lower()
    proximal_mu = config.get('federated', {}).get('proximal_mu', 0.1)

    def fit_config(server_round: int) -> Dict[str, fl.common.Scalar]:
        fit_cfg = {"server_round": server_round}
        if strategy_name == 'fedprox':
            fit_cfg["proximal_mu"] = proximal_mu
        return fit_cfg
    return fit_config


def start_global_server(port, config, min_clients: Optional[int] = None):
    logger.info(f"[Global] Starting Global Server on port {port}...")

    # Set seed for reproducibility
    seed = config.get('experiment', {}).get('seed', 42)
    set_seed(seed)

    architecture = config.get('federated', {}).get('architecture', 'flat').lower()
    strategy_name = config.get('federated', {}).get('strategy', 'fedavg').lower()

    if min_clients is not None:
        expected_clients = min_clients
        logger.info(f"[Global] Mode: OVERRIDE. Forcing min_clients={min_clients} for local test.")
    elif architecture == 'hierarchical':
        expected_clients = len(config['network']['countries'])
        logger.info(f"[Global] Mode: HIERARCHICAL. Waiting for {expected_clients} Country Servers.")
    else:
        expected_clients = sum(len(c['clients']) for c in config['network']['countries'].values())
        logger.info(f"[Global] Mode: FLAT. Waiting for {expected_clients} individual Clients.")

    logger.info(f"[Global] Strategy: {strategy_name}")

    # RealTimeLogger initialization
    if _rt_logger:
        _rt_logger.init_experiment(config)
        _rt_logger.update_training_status("training", current_round=0)

    # CommTracker initialization
    input_dim = config.get('model', {}).get('input_dim', 78)
    num_classes = config.get('model', {}).get('num_classes', 2)
    model_type = config.get('model_type', config.get('model', {}).get('type', 'mlp'))
    dummy_model = get_model(model_type, input_dim=input_dim, num_classes=num_classes)
    comm_tracker = CommTracker(model=dummy_model, n_clients=expected_clients)

    first_round_eval_done = [False]  # Track first round evaluation

    def evaluate_metrics_aggregation_fn(results):
        if not results:
            return {}
        total_examples = sum([num_examples for num_examples, _ in results])
        aggregated_metrics = {}

        if _rt_logger:
            for num_examples, m in results:
                cid = m.get("cid")
                if cid:
                    _rt_logger.update_client(
                        client_id=str(cid),
                        status='evaluating',
                        accuracy=float(m.get('accuracy', 0.0)),
                        loss=float(m.get('client_loss', 0.0)),
                        detection_rate=float(m.get('detection_rate', 0.0)),
                        f1_score=float(m.get('f1_score', 0.0)),
                        precision=float(m.get('precision', 0.0)),
                        fpr=float(m.get('fpr', 0.0))
                    )

        # Build aggregated dictionary properly
        if results and results[0] and len(results[0]) > 1:
            for key in results[0][1].keys():
                if isinstance(results[0][1][key], (int, float)):
                    w_sum = sum([num_examples * m.get(key, 0.0) for num_examples, m in results])
                    aggregated_metrics[key] = w_sum / total_examples
            # Update real-time logger with global metrics
            if _rt_logger:
                _rt_logger.update_global(**aggregated_metrics)

        return aggregated_metrics

    strategy = get_strategy(
        strategy_name=strategy_name,
        config=config,
        save_label="global",
        num_clients=expected_clients,
        on_fit_config_fn=_make_fit_config_fn(config)
    )

    # Patch the strategy with the evaluation function
    strategy.evaluate_metrics_aggregation_fn = evaluate_metrics_aggregation_fn

    # Patch aggregate_fit to log comms, divergence, and current round
    original_aggregate_fit = strategy.aggregate_fit

    def custom_aggregate_fit(server_round, results, failures):
        # Log round start message (both console and file)
        logger.info(f"\033[92m[global] Round {server_round}/{config['federated']['num_rounds_global']}: Aggregating from {len(results)} clients...\033[0m")

        agg_weights, metrics_aggregated = original_aggregate_fit(server_round, results, failures)

        if _rt_logger and agg_weights is not None:
            # Log communication
            comm_tracker.log_round(server_round, participating_clients=len(results))
            comm_info = comm_tracker.round_logs[-1]
            _rt_logger.log_communication(server_round, comm_info['upload_bytes'] / (1024 * 1024),
                                         comm_info['download_bytes'] / (1024 * 1024))

            # Calculate weight divergence
            divergences = {}

            global_params = fl.common.parameters_to_ndarrays(agg_weights)
            global_flat = np.concatenate([p.flatten() for p in global_params])
            global_tensor = torch.tensor(global_flat, dtype=torch.float32)
            for client_proxy, fit_res in results:
                cid = fit_res.metrics.get('cid', 'unknown') if fit_res.metrics and 'cid' in fit_res.metrics else 'unknown'
                client_params = fl.common.parameters_to_ndarrays(fit_res.parameters)
                client_flat = np.concatenate([p.flatten() for p in client_params])
                client_tensor = torch.tensor(client_flat, dtype=torch.float32)
                cos_sim = F.cosine_similarity(global_tensor.unsqueeze(0), client_tensor.unsqueeze(0)).item()
                divergences[str(cid)] = max(0.0, 1.0 - cos_sim)
                _rt_logger.update_weight_divergence(divergences)
            # Update training status round here, not in evaluate!
            _rt_logger.update_training_status("training", current_round=server_round)

            # Print successful completion message (both console and file)
            logger.info(f"\033[92m[global] Round {server_round}: Complete - Saved aggregated weights\033[0m")

            return agg_weights, metrics_aggregated

    strategy.aggregate_fit = custom_aggregate_fit

    # Run server
    logger.info("=" * 60)
    logger.info(f"[Global] Starting {config['federated']['num_rounds_global']} rounds of training...")
    logger.info("=" * 60)
    hist = fl.server.start_server(
        server_address=f"0.0.0.0:{port}",
        config=fl.server.ServerConfig(num_rounds=config['federated']['num_rounds_global']),
        strategy=strategy,
    )

    logger.info("[Global] Training complete.")
    logger.info("=" * 60)
    logger.info(f"Log file: {log_file}")
    logger.info("=" * 60)
    if _rt_logger:
        _rt_logger.update_training_status("complete")
    return hist


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Global Server")
    parser.add_argument("--port", type=int, default=27565, help="Port to listen on")
    parser.add_argument("--config", type=str, default="config/physical_config.yaml")
    parser.add_argument("--min_clients", type=int, default=None, help="Override minimum expected clients mapping")
    args = parser.parse_args()

    with open(args.config, 'r') as f:
        config = yaml.safe_load(f)

    start_global_server(args.port, config, min_clients=args.min_clients)

