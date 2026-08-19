import os
import sys
import yaml
import time
import subprocess

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from data_pipeline.feature_unifier import prepare_all_dummy_data
from simulation.attack_simulator import simulate_attack
from utils.metrics_logger import MetricsLogger
from utils.incident_response import IncidentResponseLog
import torch
from data_pipeline.data_loader import get_dataloader
from models.factory import get_model
from utils.experiment_manager import set_seed

def run_experiment(config_path="config/default_config.yaml"):
    """Orchestrates the hierarchical FL setup."""
    print("=== Starting FL-NIDS Experiment ===")
    with open(config_path, 'r') as f:
        config = yaml.safe_load(f)

    # Set seed for reproducibility
    seed = config.get('experiment', {}).get('seed', 42)
    set_seed(seed)

    # 1. Prepare Data
    print("1. Preparing Data (Unified Space mapping)...")
    prepare_all_dummy_data()

    # 2. Start Servers and Clients
    # In a real distributed system, these would run on different machines.
    # Here, we simulate them using subprocesses.
    print("\n2. Launching Hierarchical FL Training...")

    processes = []
    # Note: Flower doesn't trivially support true multi-tier hierarchical aggregation out-of-the-box
    # For this simulation script, we run Country Servers to aggregate their clients locally,
    # then sequentially average those Country Models.
    # A true continuous hierarchy requires custom Server implementations which are complex to script here.

    # Simulating Country-level training
    hierarchy = config.get('hierarchy', config.get('network', {}).get('countries', {}))
    for country, data in hierarchy.items():
        port = data.get('port', 8080) # fallback port
        clients = data.get('clients', [])
        # We start the Country Server in a subprocess
        server_cmd = [sys.executable, "federated/server_country.py",
                      "--country", country, "--port", str(port), "--config", config_path]
        server_p = subprocess.Popen(server_cmd)
        processes.append(server_p)
        time.sleep(2) # Give server time to start

        # Start Clients for this country
        for client_id in clients:
            client_cmd = [sys.executable, "federated/client.py",
                          "--cid", client_id, "--port", str(port), "--config", config_path]
            client_p = subprocess.Popen(client_cmd)
            processes.append(client_p)
            time.sleep(1)

    # Wait for all Country-level training to complete
    print(f"Waiting for {len(processes)} processes to finish training...")
    for p in processes:
        p.wait()
    print("Country-level training complete.")

    # In a fully fleshed out Flower Hierarchical setup, the Country Servers would now act as
    # clients and connect to `server_global.py`. For this MVP, we will simulate the final
    # attack evaluation using the trained models.

    # 3. Attack Simulation & Evaluation
    print("\n3. Simulating Attacks and Evaluating Models...")
    logger = MetricsLogger()
    ir_log = IncidentResponseLog()
    model_type = config.get('model', {}).get('type', config.get('model_type', 'mlp'))
    input_dim = config.get('model', {}).get('input_dim', config.get('input_dim', 20))
    num_classes = config.get('model', {}).get('num_classes', config.get('num_classes', 2))
    experiment_name = f"{model_type}_{config.get('federated', {}).get('strategy', 'fedavg')}"

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model = get_model(model_type, input_dim, num_classes).to(device)

    # Load the trained global model if available
    global_model_path = "models/global_model_final.pth"
    if os.path.exists(global_model_path):
        model.load_state_dict(torch.load(global_model_path, map_location=device, weights_only=True))
        print(f"Loaded trained global model from {global_model_path}")
    else:
        print(f"Warning: {global_model_path} not found. Using initialized model for evaluation.")
        print("         Run full FL training first to get meaningful evaluation results.")

    for i in range(1, 10):
        client_id = f"Client_{i:02d}"
        # Inject attacks into client test set
        attack_file = simulate_attack(client_id, attack_ratio=0.2)

        # Load mixed data
        training_cfg = config.get('training', config.get('learning', {}))
        train_loader, test_loader, _ = get_dataloader(attack_file, batch_size=training_cfg.get('batch_size', 32))

        # Evaluate model against mixed traffic
        model.eval()
        all_preds = []
        all_targets = []
        with torch.no_grad():
            for data, target in test_loader:
                data, target = data.to(device), target.to(device)
                output = model(data)
                pred = output.argmax(dim=1).flatten()

                # If an attack was PREDICTED (pred == 1), fire Incident Response
                preds = pred.cpu().numpy()
                targets = target.cpu().numpy()
                for idx, p in enumerate(preds):
                    # We just log a sample of detections to avoid huge IR logs
                    if p == 1 and len(all_preds) < 20:
                        # Feature column 0 is protocol, column 1 is flow_duration in our Unified Space
                        protocol = data[idx][0].item()
                        flow_duration = data[idx][1].item()
                        ir_log.log_incident(client_id, protocol, flow_duration)

                all_preds.extend(preds)
                all_targets.extend(targets)

        # Log metrics
        logger.log_evaluation(experiment_name, client_id, all_targets, all_preds)

    # 4. Save Metrics
    logger.save()
    print("=== Experiment Complete ===")

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Run FL-NIDS Experiment")
    parser.add_argument("--config", type=str, default="config/default_config.yaml")
    args = parser.parse_args()
    run_experiment(args.config)
