import flwr as fl
import torch
from collections import OrderedDict
import yaml
import os
import sys
import pandas as pd

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from models.factory import get_model

class CountryBridgeClient(fl.client.NumPyClient):
    """
    This client represents a whole Country in the hierarchical FL setup.
    Instead of training on a local dataset, it holds the globally aggregated weights
    from the local Country Server, and passes them up to the Global Server.
    When the Global Server sends new global weights down, it applies them locally.
    """
    def __init__(self, country_name, config, weights_path):
        self.country_name = country_name
        self.config = config
        self.weights_path = weights_path
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

        # We need a model instance just to handle the state dict parsing
        model_type = config.get('model', {}).get('type', config.get('model_type', 'mlp'))
        input_dim = config.get('model', {}).get('input_dim', config.get('input_dim', 78))
        num_classes = config.get('model', {}).get('num_classes', config.get('num_classes', 2))
        self.model = get_model(model_type, input_dim, num_classes).to(self.device)

        # In a real scenario, we'd load the aggregated weights saved by server_country.py here
        # For prototype simplicity, if the file exists we load it, else we use initialized weights.
        try:
            state_dict = torch.load(self.weights_path, weights_only=True)
            self.model.load_state_dict(state_dict)
            print(f"[{self.country_name}] Loaded aggregated weights to send to Global.")
        except FileNotFoundError:
            print(f"[{self.country_name}] Warning: No aggregated weights found at {self.weights_path}. Using initialized.")

        # Compute total samples across all clients in this country for accurate weighting
        self.total_samples = self._compute_total_samples()

    def _compute_total_samples(self):
        """Sum the number of rows across all client CSVs assigned to this country."""
        total = 0
        PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        try:
            country_clients = self.config['network']['countries'][self.country_name]['clients']
            for cid in country_clients:
                csv_path = os.path.join(PROJECT_ROOT, "data", "processed", f"{cid}.csv")
                if os.path.exists(csv_path):
                    # Count lines efficiently without loading entire CSV into memory
                    with open(csv_path, 'r', encoding='utf-8') as f:
                        # subtract 1 for header
                        total += sum(1 for _ in f) - 1
        except Exception as e:
            print(f"[{self.country_name}] Could not compute sample count: {e}. Using estimate.")
            total = 5000  # Reasonable fallback
        return max(total, 1)  # Avoid returning 0

    def get_parameters(self, config):
        # Send the aggregated country weights to the global server
        return [val.cpu().numpy() for _, val in self.model.state_dict().items()]

    def set_parameters(self, parameters):
        params_dict = zip(self.model.state_dict().keys(), parameters)
        state_dict = OrderedDict({k: torch.tensor(v) for k, v in params_dict})
        self.model.load_state_dict(state_dict, strict=True)

        # Save the new global weights so the Country Server can use them next round
        torch.save(self.model.state_dict(), self.weights_path)
        print(f"[{self.country_name}] Received new global weights. Saved to {self.weights_path}.")

    def fit(self, parameters, config):
        # We don't train here. We just accept the parameters, and immediately return
        # our locally aggregated parameters (which were updated during Country Server training).

        # We "fake" the fit by just returning our parameters.
        # The number of samples returned could be the sum of all client samples in the country.
        return self.get_parameters(config={}), self.total_samples, {}

    def evaluate(self, parameters, config):
        # The Global server evaluates. We just accept the new parameters.
        self.set_parameters(parameters)
        return 0.0, self.total_samples, {"accuracy": 0.0}

def start_bridge_client(country_name, global_ip, global_port, config, weights_path):
    client = CountryBridgeClient(country_name, config, weights_path)
    print(f"[{country_name}] Bridge connecting to Global Server at {global_ip}:{global_port}...")
    fl.client.start_client(server_address=f"{global_ip}:{global_port}", client=client.to_client())

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Country to Global Bridge Client")
    parser.add_argument("--country", type=str, required=True, help="Country name (e.g., country_A)")
    parser.add_argument("--global_ip", type=str, required=True, help="Global Server IP")
    parser.add_argument("--global_port", type=int, required=True, help="Global Server Port")
    parser.add_argument("--weights_path", type=str, required=True, help="Path to aggregated model weights")
    parser.add_argument("--config", type=str, default="config/physical_config.yaml")
    args = parser.parse_args()

    with open(args.config, 'r') as f:
        config = yaml.safe_load(f)

    start_bridge_client(args.country, args.global_ip, args.global_port, config, args.weights_path)
