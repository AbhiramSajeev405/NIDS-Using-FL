"""
Real-Time Event Logger for FL-NIDS Live Dashboard.

Provides a shared-state JSON file (`live_state.json`) that is atomically
written by training processes and read by the dashboard backend via
WebSocket push. Replaces CSV file-polling with structured event streaming.

Usage:
    logger = RealTimeLogger()
    logger.update_client("Client_01", round=3, loss=0.45, accuracy=0.91)
    logger.update_global(round=3, accuracy=0.88)
    logger.log_incident("Client_02", "DDoS", "Block UDP")

The dashboard backend watches `live_state.json` for changes and pushes
updates to all connected WebSocket clients.
"""

import os
import json
import time
import threading
from datetime import datetime

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_DEFAULT_STATE_FILE = os.path.join(_PROJECT_ROOT, "dashboard", "live_state.json")


class RealTimeLogger:
    """Thread-safe real-time state manager for the live dashboard."""

    def __init__(self, state_file=None, max_incidents=100, max_history=500, init_file=True):
        """
        Args:
            state_file: Path to the shared JSON state file
            max_incidents: Max incidents to keep in memory
            max_history: Max round history entries to keep
            init_file: If True, nukes existing state and creates a default. If False, tries to load existing first.
        """
        self.state_file = state_file or _DEFAULT_STATE_FILE
        os.makedirs(os.path.dirname(self.state_file), exist_ok=True)
        self._lock = threading.Lock()
        self.max_incidents = max_incidents
        self.max_history = max_history

        # Initialize state
        loaded = False
        if not init_file and os.path.exists(self.state_file):
            try:
                with open(self.state_file, 'r') as f:
                    self.state = json.load(f)
                loaded = True
            except Exception:
                pass
                
        if not loaded:
            self.state = self._default_state()
            self._flush()

    def _default_state(self):
        """Create a fresh default state structure."""
        return {
            "meta": {
                "experiment_name": "",
                "model_type": "",
                "strategy": "",
                "architecture": "",
                "start_time": datetime.now().isoformat(),
                "last_update": datetime.now().isoformat(),
            },
            "training": {
                "status": "idle",           # idle | training | evaluating | complete
                "current_round": 0,
                "total_rounds": 0,
                "elapsed_seconds": 0,
            },
            "global_metrics": {
                "accuracy": 0.0,
                "f1_score": 0.0,
                "detection_rate": 0.0,
                "false_positive_rate": 0.0,
                "loss": 0.0,
            },
            "clients": {},                  # client_id -> {status, metrics, country}
            "countries": {},                # country_id -> {status, metrics, clients}
            "convergence_history": [],      # [{round, accuracy, loss, f1, ...}, ...]
            "communication": {
                "total_upload_mb": 0.0,
                "total_download_mb": 0.0,
                "per_round": [],            # [{round, upload_mb, download_mb}, ...]
            },
            "communication_history": [],    # alias for frontend
            "anomaly": {
                "history": [],              # [{round, mean_score, max_score}, ...]
                "current_mean": 0.0,
                "above_threshold": 0
            },
            "weight_divergence": {},        # client_id -> cosine_distance
            "incidents": [],                # [{timestamp, client_id, attack_type, action, status}, ...]
            "timeline": [],                 # [{name, category, duration_ms}, ...]
            "fairness": {
                "jains_index": 0.0,
                "worst_client": "",
                "best_client": "",
                "accuracy_std": 0.0,
            },
        }

    def init_experiment(self, config):
        """Initialize state from experiment config.

        Args:
            config: Full experiment config dict
        """
        with self._lock:
            self.state = self._default_state()

            # Meta
            self.state["meta"]["experiment_name"] = config.get("experiment", {}).get("name", "unnamed")
            self.state["meta"]["model_type"] = config.get("model_type", config.get("model", {}).get("type", "mlp"))
            self.state["meta"]["strategy"] = config.get("federated", {}).get("strategy", "fedavg")
            self.state["meta"]["architecture"] = config.get("architecture", "flat")
            self.state["meta"]["start_time"] = datetime.now().isoformat()
            
            # Map defenses to UI
            self.state["defenses"] = config.get("defense", {})

            # Training
            fed_cfg = config.get("federated", {})
            self.state["training"]["total_rounds"] = fed_cfg.get("num_rounds_global", 10)

            # Countries & clients
            hierarchy = config.get("hierarchy", config.get("network", {}).get("countries", {}))
            for country_id, country_data in hierarchy.items():
                clients = country_data.get("clients", [])
                self.state["countries"][country_id] = {
                    "status": "idle",
                    "metrics": {"accuracy": 0.0, "loss": 0.0},
                    "clients": clients,
                }
                for cid in clients:
                    self.state["clients"][cid] = {
                        "status": "idle",
                        "country": country_id,
                        "metrics": {
                            "accuracy": 0.0,
                            "f1_score": 0.0,
                            "detection_rate": 0.0,
                            "loss": 0.0,
                        },
                    }

            self._flush()

    def update_training_status(self, status, current_round=None):
        """Update global training status.

        Args:
            status: 'idle', 'training', 'evaluating', 'complete'
            current_round: Current FL round number
        """
        with self._lock:
            self.state["training"]["status"] = status
            if current_round is not None:
                self.state["training"]["current_round"] = current_round
            start = datetime.fromisoformat(self.state["meta"]["start_time"])
            self.state["training"]["elapsed_seconds"] = int((datetime.now() - start).total_seconds())
            self._flush()

    def update_client(self, client_id, status=None, **metrics):
        """Update a client's status and metrics.

        Args:
            client_id: e.g. 'Client_01'
            status: 'idle', 'training', 'evaluating', 'done', 'dead'
            **metrics: Metric key-value pairs (accuracy, loss, f1_score, etc.)
        """
        with self._lock:
            if client_id not in self.state["clients"]:
                self.state["clients"][client_id] = {
                    "status": "idle",
                    "country": "unknown",
                    "metrics": {},
                }
            if status:
                self.state["clients"][client_id]["status"] = status
            if metrics:
                self.state["clients"][client_id]["metrics"].update(metrics)
            self._flush()

    def update_country(self, country_id, status=None, **metrics):
        """Update a country server's status and metrics.

        Args:
            country_id: e.g. 'country_A'
            status: 'idle', 'aggregating', 'done'
            **metrics: Aggregated metric values
        """
        with self._lock:
            if country_id not in self.state["countries"]:
                self.state["countries"][country_id] = {
                    "status": "idle",
                    "metrics": {},
                    "clients": [],
                }
            if status:
                self.state["countries"][country_id]["status"] = status
            if metrics:
                self.state["countries"][country_id]["metrics"].update(metrics)
            self._flush()

    def update_global(self, **metrics):
        """Update global model metrics (after aggregation).

        Args:
            **metrics: accuracy, f1_score, detection_rate, loss, etc.
        """
        with self._lock:
            self.state["global_metrics"].update(metrics)
            self._flush()

    def log_convergence(self, round_num, **metrics):
        """Log metrics for a completed round (for convergence charts).

        Args:
            round_num: FL round number
            **metrics: accuracy, loss, f1_score, detection_rate, etc.
        """
        with self._lock:
            entry = {"round": round_num, "timestamp": datetime.now().isoformat()}
            entry.update(metrics)
            self.state["convergence_history"].append(entry)
            # Trim history
            if len(self.state["convergence_history"]) > self.max_history:
                self.state["convergence_history"] = self.state["convergence_history"][-self.max_history:]
            self._flush()

    def mark_dead_client(self, client_id, reason="disconnected"):
        """Mark a client as dead/disconnected.

        Args:
            client_id: e.g. 'Client_01'
            reason: reason for death (disconnected, crashed, timeout)
        """
        with self._lock:
            if client_id in self.state["clients"]:
                self.state["clients"][client_id]["status"] = "dead"
                self.state["clients"][client_id]["last_seen"] = datetime.now().isoformat()
                self.state["clients"][client_id]["death_reason"] = reason
            self._flush()

    def log_communication(self, round_num, upload_mb, download_mb):
        """Log communication costs for a round.

        Args:
            round_num: FL round number
            upload_mb: Upload bytes in MB
            download_mb: Download bytes in MB
        """
        with self._lock:
            self.state["communication"]["total_upload_mb"] += upload_mb
            self.state["communication"]["total_download_mb"] += download_mb
            entry = {
                "round": round_num,
                "upload_mb": round(upload_mb, 4),
                "download_mb": round(download_mb, 4),
            }
            self.state["communication"]["per_round"].append(entry)
            self.state["communication_history"].append(entry)
            self._flush()

    def log_anomaly_round(self, round_num, mean_score, max_score, threshold_count):
        """Log aggregated anomaly scores for the timeline chart."""
        with self._lock:
            self.state["anomaly"]["current_mean"] = round(mean_score, 4)
            self.state["anomaly"]["above_threshold"] = threshold_count
            self.state["anomaly"]["history"].append({
                "round": round_num,
                "mean_score": round(mean_score, 4),
                "max_score": round(max_score, 4)
            })
            if len(self.state["anomaly"]["history"]) > self.max_history:
                self.state["anomaly"]["history"] = self.state["anomaly"]["history"][-self.max_history:]
            self._flush()

    def update_weight_divergence(self, divergences):
        """Update client-to-global weight divergence radar chart.
        Args: divergences is a dict {client_id: cosine_distance}
        """
        with self._lock:
            for cid, dist in divergences.items():
                self.state["weight_divergence"][cid] = round(float(dist), 4)
            self._flush()

    def log_incident(self, client_id, attack_type, action, status="Mitigated"):
        """Log an attack detection incident.

        Args:
            client_id: Source client
            attack_type: Type of attack detected
            action: Automated response action taken
            status: 'Mitigated', 'Investigating', 'Escalated'
        """
        with self._lock:
            self.state["incidents"].append({
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "client_id": client_id,
                "attack_type": attack_type,
                "action": action,
                "status": status,
            })
            # Trim incidents
            if len(self.state["incidents"]) > self.max_incidents:
                self.state["incidents"] = self.state["incidents"][-self.max_incidents:]
            self._flush()

    def update_fairness(self, jains_index, worst_client, best_client, accuracy_std):
        """Update fairness metrics.

        Args:
            jains_index: Jain's fairness index (0-1)
            worst_client: Client ID with worst performance
            best_client: Client ID with best performance
            accuracy_std: Standard deviation of accuracies
        """
        with self._lock:
            self.state["fairness"] = {
                "jains_index": round(jains_index, 4),
                "worst_client": worst_client,
                "best_client": best_client,
                "accuracy_std": round(accuracy_std, 4),
            }
            self._flush()

    def get_state(self):
        """Return a copy of the current state."""
        with self._lock:
            return json.loads(json.dumps(self.state))

    def _flush(self):
        """Atomically write state to disk."""
        self.state["meta"]["last_update"] = datetime.now().isoformat()
        tmp_path = self.state_file + ".tmp"
        try:
            # Preserve incidents from previous state (they get set by /api/incident endpoint)
            existing_incidents = []
            if os.path.exists(self.state_file):
                try:
                    with open(self.state_file, 'r') as f:
                        existing = json.load(f)
                        if "incidents" in existing:
                            existing_incidents = existing["incidents"]
                except:
                    pass

            # Merge existing incidents into current state
            if existing_incidents and "incidents" not in self.state:
                self.state["incidents"] = existing_incidents
            elif existing_incidents and "incidents" in self.state:
                # Merge: keep older incidents + new ones
                merged = existing_incidents + self.state["incidents"]
                # Remove duplicates
                unique = []
                seen = set()
                for inc in merged:
                    key = (inc.get("client_id"), inc.get("attack_type"), inc.get("timestamp"))
                    if key not in seen:
                        seen.add(key)
                        unique.append(inc)
                self.state["incidents"] = unique[-100:]  # Keep last 100

            with open(tmp_path, 'w') as f:
                json.dump(self.state, f, indent=2)
            # Atomic replace (Windows-safe)
            os.replace(tmp_path, self.state_file)
        except Exception as e:
            print(f"[RealTimeLogger] Warning: Failed to flush state: {e}")
