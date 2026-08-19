import os
import json
from datetime import datetime
import pandas as pd
from sklearn.metrics import f1_score, accuracy_score, confusion_matrix

class MetricsLogger:
    def __init__(self, output_dir=None):
        if output_dir is None:
            output_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logs")
        self.output_dir = output_dir
        os.makedirs(self.output_dir, exist_ok=True)
        self.timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.metrics_file = os.path.join(self.output_dir, f"experiment_metrics_{self.timestamp}.json")
        self.metrics = []

    def log_evaluation(self, experiment_name, client_id, true_labels, predictions):
        """Calculates and logs metrics for a specific client."""
        accuracy = accuracy_score(true_labels, predictions)
        f1 = f1_score(true_labels, predictions, zero_division=0)
        cm = confusion_matrix(true_labels, predictions, labels=[0, 1])

        # Avoid division by zero
        tn, fp, fn, tp = cm.ravel() if cm.size == 4 else (0, 0, 0, 0)
        detection_rate = tp / (tp + fn) if (tp + fn) > 0 else 0
        false_positive_rate = fp / (fp + tn) if (fp + tn) > 0 else 0

        record = {
            "experiment": experiment_name,
            "client_id": client_id,
            "accuracy": accuracy,
            "f1_score": f1,
            "detection_rate": detection_rate,
            "false_positive_rate": false_positive_rate,
            "confusion_matrix": {"tn": int(tn), "fp": int(fp), "fn": int(fn), "tp": int(tp)}
        }
        self.metrics.append(record)
        print(f"[{client_id}] Eval -> Acc: {accuracy:.4f} | F1: {f1:.4f} | DR: {detection_rate:.4f} | FPR: {false_positive_rate:.4f}")

    def save(self):
        """Saves all logged metrics to JSON and CSV."""
        with open(self.metrics_file, 'w') as f:
            json.dump(self.metrics, f, indent=4)

        csv_file = self.metrics_file.replace('.json', '.csv')
        df = pd.DataFrame(self.metrics)
        # Flatten confusion matrix for CSV
        if not df.empty:
            cm_df = pd.json_normalize(df['confusion_matrix'])
            df = df.drop('confusion_matrix', axis=1).join(cm_df)
            df.to_csv(csv_file, index=False)
            print(f"Metrics saved to {csv_file}")
