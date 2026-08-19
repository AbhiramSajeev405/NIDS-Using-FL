"""
Local Personalization for Federated Learning.

After global FL training is complete, each client fine-tunes the
global model on its local data for a few epochs. This produces
personalized models that may perform better on each client's
specific data distribution.

Key comparison:
  - Global model accuracy (same model for all)
  - Personalized model accuracy (global + local fine-tuning)

Reference: Fallah et al. 'Personalized Federated Learning with Moreau Envelopes' (NeurIPS 2020)

Usage:
    from federated.personalization import personalize_client
    results = personalize_client(global_model_path, client_data_path, config)
"""

import os
import sys
import copy
import torch
import torch.nn as nn
import numpy as np
import pandas as pd
from collections import OrderedDict
from sklearn.metrics import accuracy_score, f1_score, roc_auc_score

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from models.factory import get_model
from data_pipeline.data_loader import get_dataloader


def personalize_client(global_model_path, data_path, config,
                        personalization_epochs=3, personalization_lr=0.0001):
    """Fine-tune the global model on a single client's local data.

    Args:
        global_model_path: Path to the saved global model (.pth)
        data_path: Path to the client's local CSV data
        config: Full experiment config dict
        personalization_epochs: Number of local fine-tuning epochs
        personalization_lr: Learning rate for fine-tuning (typically lower)

    Returns:
        Dict with 'global' and 'personalized' metrics for comparison
    """
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

    model_type = config.get('model', {}).get('type', config.get('model_type', 'mlp'))
    input_dim = config.get('model', {}).get('input_dim', config.get('input_dim', 78))
    num_classes = config.get('model', {}).get('num_classes', config.get('num_classes', 2))

    training_cfg = config.get('training', config.get('learning', {}))
    batch_size = training_cfg.get('batch_size', 32)

    train_loader, test_loader, _ = get_dataloader(data_path, batch_size=batch_size)

    # Calculate class weights for imbalanced data (Fixes high FPR)
    class_weights = _calculate_class_weights(data_path)
    if class_weights is not None:
        criterion = nn.CrossEntropyLoss(weight=torch.tensor(class_weights, dtype=torch.float32).to(device))
    else:
        criterion = nn.CrossEntropyLoss()

    # --- Evaluate global model (before personalization) ---
    global_model = get_model(model_type, input_dim, num_classes).to(device)
    global_model.load_state_dict(torch.load(global_model_path, map_location=device, weights_only=True))

    global_metrics = _evaluate(global_model, test_loader, criterion, device)

    # --- Fine-tune on local data ---
    personal_model = get_model(model_type, input_dim, num_classes).to(device)
    personal_model.load_state_dict(torch.load(global_model_path, map_location=device, weights_only=True))

    optimizer = torch.optim.Adam(personal_model.parameters(), lr=personalization_lr)

    personal_model.train()
    for epoch in range(personalization_epochs):
        for data, target in train_loader:
            data, target = data.to(device), target.to(device)
            optimizer.zero_grad()
            output = personal_model(data)
            loss = criterion(output, target)
            loss.backward()
            optimizer.step()

    # --- Evaluate personalized model ---
    personal_metrics = _evaluate(personal_model, test_loader, criterion, device)

    return {
        'global': global_metrics,
        'personalized': personal_metrics,
        'improvement': {
            k: personal_metrics[k] - global_metrics[k]
            for k in global_metrics if isinstance(global_metrics[k], float)
        }
    }


def personalize_all_clients(global_model_path, config,
                              personalization_epochs=3,
                              personalization_lr=0.0001):
    """Run personalization for all clients and compare results.

    Args:
        global_model_path: Path to global model
        config: Full experiment config
        personalization_epochs: Fine-tuning epochs
        personalization_lr: Fine-tuning learning rate

    Returns:
        Dict mapping client_id -> results
    """
    PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    data_dir = os.path.join(PROJECT_ROOT, "data", "processed")

    print("=" * 60)
    print("LOCAL PERSONALIZATION")
    print(f"  Global model: {global_model_path}")
    print(f"  Fine-tuning: {personalization_epochs} epochs @ lr={personalization_lr}")
    print("=" * 60)

    all_results = {}
    global_accs = []
    personal_accs = []

    for i in range(1, 10):
        cid = f"Client_{i:02d}"
        data_path = os.path.join(data_dir, f"{cid}.csv")
        if not os.path.exists(data_path):
            print(f"  [{cid}] Data not found, skipping")
            continue

        result = personalize_client(
            global_model_path, data_path, config,
            personalization_epochs, personalization_lr
        )
        all_results[cid] = result

        g_acc = result['global']['accuracy']
        p_acc = result['personalized']['accuracy']
        diff = result['improvement']['accuracy']
        direction = "↑" if diff > 0 else "↓" if diff < 0 else "="

        global_accs.append(g_acc)
        personal_accs.append(p_acc)

        print(f"  [{cid}] Global: {g_acc:.4f}  Personal: {p_acc:.4f}  ({direction}{abs(diff):.4f})")

    if global_accs:
        print(f"\n  {'='*40}")
        print(f"  Average Global:       {np.mean(global_accs):.4f} ± {np.std(global_accs):.4f}")
        print(f"  Average Personalized: {np.mean(personal_accs):.4f} ± {np.std(personal_accs):.4f}")
        print(f"  Average Improvement:  {np.mean(personal_accs) - np.mean(global_accs):.4f}")
        print(f"  {'='*40}")

    return all_results


def _evaluate(model, test_loader, criterion, device):
    """Evaluate a model and return metrics."""
    model.eval()
    all_preds, all_targets, all_probs = [], [], []
    total_loss = 0.0

    with torch.no_grad():
        for data, target in test_loader:
            data, target = data.to(device), target.to(device)
            output = model(data)
            total_loss += criterion(output, target).item()
            probs = torch.softmax(output, dim=1)
            preds = output.argmax(dim=1)
            all_preds.extend(preds.cpu().numpy())
            all_targets.extend(target.cpu().numpy())
            all_probs.extend(probs[:, 1].cpu().numpy())

    acc = accuracy_score(all_targets, all_preds)
    f1 = f1_score(all_targets, all_preds, average='weighted', zero_division=0)

    try:
        auc = roc_auc_score(all_targets, all_probs)
    except ValueError:
        auc = 0.0

    return {
        'accuracy': acc,
        'f1_score': f1,
        'auc_roc': auc,
        'loss': total_loss / max(1, len(test_loader)),
    }


def _calculate_class_weights(data_path):
    """Calculate class weights from data to handle imbalance."""
    try:
        if not os.path.exists(data_path):
            return None

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

        # Calculate weights: w_c = n_samples / (n_classes * n_samples_c)
        total_samples = len(df)
        num_classes = len(label_counts)

        weights = []
        for i in range(num_classes):
            class_count = label_counts.get(i, 1)
            if class_count > 0:
                weight = total_samples / (num_classes * class_count)
            else:
                weight = 1.0
            weights.append(weight)

        return weights

    except Exception as e:
        print(f"Could not calculate class weights: {e}")
        return None
