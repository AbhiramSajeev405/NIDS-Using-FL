import os
import pandas as pd
from datetime import datetime

class IncidentResponseLog:
    def __init__(self, log_dir=None):
        if log_dir is None:
            log_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logs")
        self.log_dir = log_dir
        os.makedirs(self.log_dir, exist_ok=True)
        self.log_file = os.path.join(self.log_dir, f"incident_response_log.csv")

        # Initialize the file if it doesn't exist
        if not os.path.exists(self.log_file):
            df = pd.DataFrame(columns=[
                "timestamp", "client_id", "attack_type", "protocol", "action_taken", "status"
            ])
            df.to_csv(self.log_file, index=False)

    def log_incident(self, client_id, protocol, flow_duration):
        """Logs a single detected attack and assigns a simulated automated response."""

        # Simulate some logic: if duration is long, maybe it's a brute force. If UDP, maybe DDoS.
        attack_type = "Unknown"
        action = "Logged"

        if protocol == 17: # UDP
            attack_type = "Potential UDP Flood (DDoS)"
            action = "Block UDP Traffic from Source"
        elif protocol == 6 and flow_duration > 5000:
            attack_type = "Potential Brute Force / Exfiltration"
            action = "Rate Limit Connection & Alert SOC"
        elif protocol == 6:
            attack_type = "Suspicious TCP Flow"
            action = "Reset TCP Connection"
        else:
            attack_type = "Generic Anomaly"
            action = "Flag for Review"

        new_incident = pd.DataFrame([{
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "client_id": client_id,
            "attack_type": attack_type,
            "protocol": protocol,
            "action_taken": action,
            "status": "Mitigated"
        }])

        # Append to CSV
        new_incident.to_csv(self.log_file, mode='a', header=False, index=False)
        print(f"[Incident Response] Detected {attack_type} on {client_id} -> {action}")
