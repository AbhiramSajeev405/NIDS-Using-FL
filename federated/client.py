import flwr as fl
import torch
import torch.nn as nn
from collections import OrderedDict
import sys
import os
import numpy as np
import pandas as pd
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from data_pipeline.data_loader import get_dataloader
from models.factory import get_model
from utils.experiment_manager import set_seed

# Optional real-time dashboard integration
try:
    from utils.real_time_logger import RealTimeLogger
    _rt_logger = None # Disabled locally to prevent disk wipe race conditions
except Exception:
    _rt_logger = None

# Optional timeline tracking
try:
    from utils.timeline_tracker import TimelineTracker
    _timeline = TimelineTracker()
except Exception:
    _timeline = None

# Optional anomaly scoring
try:
    from utils.anomaly_scorer import AnomalyScorer
    _has_anomaly_scorer = True
except Exception:
    _has_anomaly_scorer = False


def _build_optimizer(model, config):
    """Build optimizer from config. Supports adam, sgd, adamw."""
    training = config.get('training', config.get('learning', {}))
    opt_name = training.get('optimizer', 'adam').lower()
    lr = training.get('lr', 0.001)
    weight_decay = training.get('weight_decay', 0.0)
    momentum = training.get('momentum', 0.9)

    if opt_name == 'sgd':
        return torch.optim.SGD(model.parameters(), lr=lr, momentum=momentum, weight_decay=weight_decay)
    elif opt_name == 'adamw':
        return torch.optim.AdamW(model.parameters(), lr=lr, weight_decay=weight_decay)
    else:  # default: adam
        return torch.optim.Adam(model.parameters(), lr=lr, weight_decay=weight_decay)


def _build_scheduler(optimizer, config, epochs):
    """Build LR scheduler from config. Supports none, step, cosine."""
    training = config.get('training', config.get('learning', {}))
    sched_name = training.get('lr_scheduler', 'none').lower()

    if sched_name == 'step':
        step_size = training.get('lr_step_size', max(1, epochs // 2))
        gamma = training.get('lr_gamma', 0.5)
        return torch.optim.lr_scheduler.StepLR(optimizer, step_size=step_size, gamma=gamma)
    elif sched_name == 'cosine':
        return torch.optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=epochs)
    else:
        return None


class ClientTrainer(fl.client.NumPyClient):
    def __init__(self, cid, config):
        self.cid = cid
        self.config = config
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

        # Load Model
        model_type = self.config.get('model', {}).get('type', self.config.get('model_type', 'mlp'))
        input_dim = self.config.get('model', {}).get('input_dim', self.config.get('input_dim', 78))
        num_classes = self.config.get('model', {}).get('num_classes', self.config.get('num_classes', 2))
        self.model = get_model(model_type, input_dim, num_classes).to(self.device)
        self.is_autoencoder = model_type.lower() == 'autoencoder'

        # Load Data
        PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        data_path = os.path.join(PROJECT_ROOT, "data", "processed", f"{self.cid}.csv")

        training = self.config.get('training', self.config.get('learning', {}))
        batch_size = training.get('batch_size', 32)
        self.train_loader, self.test_loader, self.dataset = get_dataloader(data_path, batch_size=batch_size)

        # Calculate class weights for imbalanced data (Fixes high FPR ~27-28%)
        self.class_weights = self._calculate_class_weights(data_path)
        if self.class_weights is not None:
            self.criterion = nn.CrossEntropyLoss(weight=torch.tensor(self.class_weights, dtype=torch.float32).to(self.device))
        else:
            self.criterion = nn.CrossEntropyLoss()

        self.optimizer = _build_optimizer(self.model, self.config)

        epochs = training.get('epochs', 5)
        self.scheduler = _build_scheduler(self.optimizer, self.config, epochs)

        # Store global params for defenses (updated each round)
        self.global_params_numpy = None

    def _calculate_class_weights(self, data_path):
        """Calculate class weights from data to handle imbalance.

        Root cause of high FPR (27-28%): Unweighted CrossEntropyLoss + class imbalance
        where models lean toward predicting the majority class.

        Returns:
            List of weights [weight_class_0, weight_class_1] or None if calculation fails
        """
        try:
            if not os.path.exists(data_path):
                return None

            # Read the CSV to count labels
            df = pd.read_csv(data_path, dtype={'protocol': object})

            # Detect label column
            if 'label' in df.columns:
                label_col = 'label'
            elif 'Label' in df.columns:
                label_col = 'Label'
            else:
                label_col = df.columns[-1]

            # Count classes
            label_counts = df[label_col].value_counts()

            if len(label_counts) < 2:
                return None

            # Calculate total samples and number of classes
            total_samples = len(df)
            num_classes = len(label_counts)

            # Calculate weights: w_c = n_samples / (n_classes * n_samples_c)
            # This gives higher weight to minority classes
            weights = []
            for i in range(num_classes):
                class_count = label_counts.get(i, 1)
                if class_count > 0:
                    weight = total_samples / (num_classes * class_count)
                else:
                    weight = 1.0
                weights.append(weight)

            print(f"[{self.cid}] Class weights calculated: {weights}")
            return weights

        except Exception as e:
            print(f"[{self.cid}] Could not calculate class weights: {e}")
            return None

    def get_parameters(self, config):
        params = [val.cpu().numpy() for _, val in self.model.state_dict().items()]

        # Apply client-side defenses before sending
        if self.global_params_numpy is not None:
            try:
                from federated.defenses import apply_client_defenses
                params = apply_client_defenses(params, self.global_params_numpy, self.config)
            except ImportError:
                pass

        return params

    def set_parameters(self, parameters):
        params_dict = zip(self.model.state_dict().keys(), parameters)
        state_dict = OrderedDict({k: torch.tensor(v) for k, v in params_dict})
        self.model.load_state_dict(state_dict, strict=True)

    def fit(self, parameters, config):
        self.set_parameters(parameters)

        # Save global params for defenses and FedProx
        self.global_params_numpy = [np.copy(p) for p in parameters]

        # Set seed for reproducibility
        seed = config.get('experiment', {}).get('seed', 42)
        set_seed(seed)

        self.model.train()

        # Initialize loss in case DataLoader is empty
        loss = torch.tensor(0.0)

        # FedProx: check if server sent proximal_mu
        proximal_mu = config.get("proximal_mu", 0.0)

        # Adaptive FedProx mu: reduce for complex models (LSTM, ResNet)
        # Fix for: FedProx crashes LSTM/ResNet accuracy from 91.8% to 81%
        model_type = self.config.get('model', {}).get('type', 'mlp').lower()
        if proximal_mu > 0 and model_type in ['lstm', 'resnet']:
            # LSTM and ResNet are destabilized by mu=0.1, use adaptive scaling
            adaptiveratio = 0.1  # Use only 10% of original mu for complex models
            proximal_mu = proximal_mu * adaptive_ratio
            print(f"[{self.cid}] FedProx: Using adaptive mu={proximal_mu:.4f} for {model_type}")

        if proximal_mu > 0:
            global_params = [val.clone().detach() for val in self.model.parameters()]

        training = self.config.get('training', self.config.get('learning', {}))
        epochs = training.get('epochs', 5)

        total_steps = 0
        if _rt_logger:
            _rt_logger.update_client(self.cid, status='training')

        # Timeline: record training start
        _train_eid = None
        if _timeline:
            _train_eid = _timeline.start_event(
                f"{self.cid} Training", "training",
                {"round": config.get('current_round', 0), "epochs": epochs}
            )
        for epoch in range(epochs):
            for data, target in self.train_loader:
                data, target = data.to(self.device), target.to(self.device)
                self.optimizer.zero_grad()

                # Autoencoder uses combined loss
                if self.is_autoencoder and hasattr(self.model, 'compute_loss'):
                    loss, _ = self.model.compute_loss(data, target, self.criterion)
                else:
                    output = self.model(data)
                    loss = self.criterion(output, target)

                # FedProx proximal term: (mu/2) * ||w - w_global||^2
                if proximal_mu > 0:
                    proximal_term = 0.0
                    for local_param, global_param in zip(self.model.parameters(), global_params):
                        proximal_term += ((local_param - global_param) ** 2).sum()
                    loss += (proximal_mu / 2.0) * proximal_term

                loss.backward()
                self.optimizer.step()
                total_steps += 1

                # Step the scheduler
                if self.scheduler is not None:
                    self.scheduler.step()

        # Timeline: record training end
        if _timeline and _train_eid:
            _timeline.end_event(_train_eid)

        # Emit metrics to live dashboard
        if _rt_logger:
            _rt_logger.update_client(self.cid, status='done', loss=loss.item())

        # Return params + training metadata (used by FedNova)
        return self.get_parameters(config={}), len(self.train_loader.dataset), {"num_steps": total_steps}

    def evaluate(self, parameters, config):
        self.set_parameters(parameters)
        self.model.eval()

        # Timeline: record evaluation start
        _eval_eid = None
        if _timeline:
            _eval_eid = _timeline.start_event(
                f"{self.cid} Eval", "evaluation",
                {"round": config.get('current_round', 0)}
            )

        loss, correct = 0.0, 0
        all_preds = []
        all_targets = []
        with torch.no_grad():
            for data, target in self.test_loader:
                data, target = data.to(self.device), target.to(self.device)
                output = self.model(data)
                loss += self.criterion(output, target).item()
                pred = output.argmax(dim=1, keepdim=True)
                correct += pred.eq(target.view_as(pred)).sum().item()
                all_preds.extend(pred.cpu().numpy().flatten())
                all_targets.extend(target.cpu().numpy().flatten())

        accuracy = correct / len(self.test_loader.dataset)
        avg_loss = loss / len(self.test_loader)

        try:
            from sklearn.metrics import precision_score, f1_score, confusion_matrix
            precision = float(precision_score(all_targets, all_preds, zero_division=0))
            f1 = float(f1_score(all_targets, all_preds, zero_division=0))
            cm = confusion_matrix(all_targets, all_preds, labels=[0, 1])
            tn, fp, fn, tp = cm.ravel()
            fpr = float(fp / (fp + tn)) if (fp + tn) > 0 else 0.0
            detection_rate = float(tp / (tp + fn)) if (tp + fn) > 0 else 0.0
        except Exception:
            precision, f1, fpr, detection_rate = 0.0, 0.0, 0.0, 0.0

        # Anomaly scoring
        anomaly_summary = {}
        if _has_anomaly_scorer and self.config.get('anomaly', {}).get('enabled', False):
            try:
                scorer = AnomalyScorer(self.model, self.device)
                anomaly_summary = scorer.score_summary(self.test_loader)
                if _rt_logger:
                    _rt_logger.update_client(
                        self.cid, anomaly_mean=anomaly_summary.get('mean', 0),
                        anomaly_high_pct=anomaly_summary.get('pct_above_80', 0)
                    )
            except Exception:
                pass  # Non-critical: anomaly scoring failed

        # Timeline: record evaluation end
        if _timeline and _eval_eid:
            _timeline.end_event(_eval_eid)

        if _rt_logger:
            _rt_logger.update_client(self.cid, status='done', accuracy=accuracy, loss=avg_loss)

        # Transmit advanced metrics cross-network back to Global Server Dashboard
        metrics = {
            "cid": self.cid,
            "accuracy": float(accuracy),
            "precision": float(precision),
            "f1_score": float(f1),
            "fpr": float(fpr),
            "detection_rate": float(detection_rate),
            "client_loss": float(avg_loss)
        }
        if anomaly_summary:
            metrics["anomaly_mean"] = anomaly_summary.get("mean", 0.0)
        return float(avg_loss), len(self.test_loader.dataset), metrics

    def start_client(cid, server_ip, server_port, config):
        client = ClientTrainer(cid, config)
        print(f"[{cid}] Starting, connecting to server at {server_ip}:{server_port}")
        fl.client.start_client(server_address=f"{server_ip}:{server_port}", client=client.to_client())

    if __name__ == "__main__":
        import argparse
        import yaml

        parser = argparse.ArgumentParser(description="Flower Client")
        parser.add_argument("--cid", type=str, required=True, help="Client ID (e.g., Client_01)")
        parser.add_argument("--server_ip", type=str, default="127.0.0.1", help="IP of the Server to connect to")
        parser.add_argument("--port", type=int, required=True, help="Port of the Server to connect to")
        parser.add_argument("--config", type=str, default="config/physical_config.yaml")
        args = parser.parse_args()

        with open(args.config, 'r') as f:
            config = yaml.safe_load(f)

        start_client(args.cid, args.server_ip, args.port, config)
