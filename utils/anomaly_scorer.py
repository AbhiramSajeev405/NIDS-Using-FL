"""
Anomaly Scorer for FL-NIDS.

Per-sample anomaly scoring pipeline. Runs inference on each data sample and
assigns a continuous anomaly score (0-1) rather than binary classification.
Enables threshold-based analysis, ROC curves, and score distribution
histograms in the live dashboard.

Usage:
    scorer = AnomalyScorer(model, device)
    scores = scorer.score_batch(data_tensor)
    results = scorer.score_dataset(dataloader)
    threshold_report = scorer.compute_threshold_metrics(scores, labels)
"""

import numpy as np
import torch
import torch.nn.functional as F


class AnomalyScorer:
    """Per-sample anomaly scoring using model softmax probabilities."""

    def __init__(self, model, device=None):
        """
        Args:
            model: Trained PyTorch nn.Module (binary classifier)
            device: torch.device (auto-detected if None)
        """
        self.model = model
        self.device = device or next(model.parameters()).device
        self.model.eval()

    def score_batch(self, data):
        """
        Compute anomaly scores for a batch of samples.

        Args:
            data: Tensor of shape (batch, features)

        Returns:
            numpy array of anomaly scores in [0, 1]
        """
        with torch.no_grad():
            data = data.to(self.device)
            output = self.model(data)

            # Handle autoencoder models (have reconstruction + classification)
            if isinstance(output, tuple):
                output = output[1]  # classification head

            probs = F.softmax(output, dim=1)
            # Attack class is class 1; score = probability of attack
            if probs.shape[1] >= 2:
                scores = probs[:, 1].cpu().numpy()
            else:
                scores = probs[:, 0].cpu().numpy()

        return scores

    def score_dataset(self, dataloader, top_k=None):
        """
        Score an entire dataset and return sorted results.

        Args:
            dataloader: PyTorch DataLoader
            top_k: If set, return only the top-k highest scoring samples

        Returns:
            List of dicts: [{index, score, label}, ...] sorted by score desc
        """
        all_scores = []
        all_labels = []
        sample_idx = 0

        with torch.no_grad():
            for data, target in dataloader:
                scores = self.score_batch(data)
                for i, score in enumerate(scores):
                    all_scores.append({
                        "index": sample_idx + i,
                        "score": float(score),
                        "label": int(target[i].item()),
                    })
                sample_idx += len(data)
                all_labels.extend(target.cpu().numpy().tolist())

        # Sort by score descending (most anomalous first)
        all_scores.sort(key=lambda x: x["score"], reverse=True)

        if top_k is not None:
            all_scores = all_scores[:top_k]

        return all_scores

    def compute_threshold_metrics(self, scores, labels, thresholds=None):
        """
        Compute precision, recall, F1 at various thresholds.

        Args:
            scores: array-like of anomaly scores
            labels: array-like of true labels (0=normal, 1=attack)
            thresholds: list of thresholds to evaluate (default: 0.1 to 0.9)

        Returns:
            List of dicts: [{threshold, precision, recall, f1, tp, fp, tn, fn}, ...]
        """
        scores = np.asarray(scores, dtype=float)
        labels = np.asarray(labels, dtype=int)

        if thresholds is None:
            thresholds = [round(t * 0.05, 2) for t in range(1, 20)]

        results = []
        for thresh in thresholds:
            preds = (scores >= thresh).astype(int)

            tp = int(np.sum((preds == 1) & (labels == 1)))
            fp = int(np.sum((preds == 1) & (labels == 0)))
            tn = int(np.sum((preds == 0) & (labels == 0)))
            fn = int(np.sum((preds == 0) & (labels == 1)))

            precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
            recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
            f1 = (2 * precision * recall / (precision + recall)
                   if (precision + recall) > 0 else 0.0)

            results.append({
                "threshold": thresh,
                "precision": round(precision, 4),
                "recall": round(recall, 4),
                "f1": round(f1, 4),
                "tp": tp, "fp": fp, "tn": tn, "fn": fn,
            })

        return results

    def score_summary(self, dataloader):
        """
        Quick summary statistics of anomaly scores across a dataset.

        Returns:
            Dict with mean, std, min, max, median, pct_above_50, pct_above_80
        """
        all_scores = []
        with torch.no_grad():
            for data, _ in dataloader:
                scores = self.score_batch(data)
                all_scores.extend(scores.tolist())

        arr = np.array(all_scores)
        return {
            "count": len(arr),
            "mean": round(float(np.mean(arr)), 4),
            "std": round(float(np.std(arr)), 4),
            "min": round(float(np.min(arr)), 4),
            "max": round(float(np.max(arr)), 4),
            "median": round(float(np.median(arr)), 4),
            "pct_above_50": round(float(np.mean(arr > 0.5) * 100), 2),
            "pct_above_80": round(float(np.mean(arr > 0.8) * 100), 2),
        }
