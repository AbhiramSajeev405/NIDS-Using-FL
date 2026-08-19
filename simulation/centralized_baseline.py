"""
Centralized Baseline for FL-NIDS.

Trains a model on ALL client data merged into one dataset.
This serves as the upper-bound benchmark — FL performance should
approach but rarely match centralized training.

Usage:
    python simulation/centralized_baseline.py --config config/local_test_config.yaml
"""

import os
import sys
import glob
import argparse
import json
import yaml
import numpy as np
import pandas as pd
import torch
import torch.nn as nn
from datetime import datetime
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import (
    accuracy_score, f1_score, precision_score, recall_score,
    roc_auc_score, confusion_matrix
)
from torch.utils.data import DataLoader, TensorDataset

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from models.factory import get_model

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def load_all_client_data(processed_dir):
    """Load and merge all client CSVs into one DataFrame."""
    csv_files = sorted(glob.glob(os.path.join(processed_dir, "Client_*.csv")))
    if not csv_files:
        raise FileNotFoundError(f"No client CSV files found in {processed_dir}")

    dfs = []
    for f in csv_files:
        df = pd.read_csv(f)
        df['_source'] = os.path.basename(f)
        dfs.append(df)
        print(f"  Loaded {os.path.basename(f)}: {len(df)} samples")

    merged = pd.concat(dfs, ignore_index=True)
    print(f"  Total: {len(merged)} samples from {len(csv_files)} clients")
    return merged


def train_centralized(config, data_dir=None, results_dir=None):
    """Train a model on all data centrally and evaluate."""
    if data_dir is None:
        data_dir = os.path.join(_PROJECT_ROOT, "data", "processed")
    if results_dir is None:
        results_dir = os.path.join(_PROJECT_ROOT, "results", "centralized_baseline")
    os.makedirs(results_dir, exist_ok=True)

    # Set seed
    seed = config.get('experiment', {}).get('seed', 42)
    torch.manual_seed(seed)
    np.random.seed(seed)

    print("=" * 60)
    print("CENTRALIZED BASELINE TRAINING")
    print("=" * 60)

    # Load all data
    print("\n[1/4] Loading all client data...")
    merged = load_all_client_data(data_dir)

    # Detect label column
    label_col = None
    for col in ['label', 'Label']:
        if col in merged.columns:
            label_col = col
            break
    if label_col is None:
        label_col = merged.columns[-1]

    drop_cols = [c for c in [label_col, '_source'] if c in merged.columns]
    X = merged.drop(drop_cols, axis=1).values
    y = merged[label_col].values

    # Split
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=seed, stratify=y
    )

    # Scale
    scaler = StandardScaler()
    X_train = scaler.fit_transform(X_train)
    X_test = scaler.transform(X_test)

    # To tensors
    X_train_t = torch.tensor(X_train, dtype=torch.float32)
    y_train_t = torch.tensor(y_train, dtype=torch.long)
    X_test_t = torch.tensor(X_test, dtype=torch.float32)
    y_test_t = torch.tensor(y_test, dtype=torch.long)

    train_loader = DataLoader(
        TensorDataset(X_train_t, y_train_t),
        batch_size=config.get('training', config.get('learning', {})).get('batch_size', 32),
        shuffle=True
    )
    test_loader = DataLoader(
        TensorDataset(X_test_t, y_test_t),
        batch_size=config.get('training', config.get('learning', {})).get('batch_size', 32),
        shuffle=False
    )

    # Build model
    model_type = config.get('model_type', 'mlp')
    input_dim = config.get('input_dim', X_train.shape[1])
    num_classes = config.get('num_classes', 2)
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

    print(f"\n[2/4] Building model: {model_type} (input={input_dim}, classes={num_classes})")
    model = get_model(model_type, input_dim, num_classes).to(device)

    # Count parameters
    total_params = sum(p.numel() for p in model.parameters())
    trainable_params = sum(p.numel() for p in model.parameters() if p.requires_grad)
    print(f"  Parameters: {total_params:,} total, {trainable_params:,} trainable")

    # Calculate class weights for imbalanced data (Fixes high FPR)
    label_counts = pd.value_counts(y_train)
    if len(label_counts) >= 2:
        total_samples = len(y_train)
        num_classes = len(label_counts)
        class_weights = []
        for i in range(num_classes):
            class_count = label_counts.get(i, 1)
            weight = total_samples / (num_classes * class_count) if class_count > 0 else 1.0
            class_weights.append(weight)
        criterion = nn.CrossEntropyLoss(weight=torch.tensor(class_weights, dtype=torch.float32))
    else:
        criterion = nn.CrossEntropyLoss()
    training_cfg = config.get('training', config.get('learning', {}))
    optimizer = torch.optim.Adam(model.parameters(), lr=training_cfg.get('lr', 0.001))

    # Simulate same total epochs as FL: rounds * local_epochs
    fl_rounds = config.get('federated', {}).get('num_rounds_global', 3)
    local_epochs = training_cfg.get('epochs', 5)
    total_epochs = fl_rounds * local_epochs

    # Train
    print(f"\n[3/4] Training for {total_epochs} epochs (= {fl_rounds} FL rounds × {local_epochs} local epochs)...")
    history = []
    for epoch in range(total_epochs):
        model.train()
        epoch_loss = 0.0
        for data, target in train_loader:
            data, target = data.to(device), target.to(device)
            optimizer.zero_grad()
            output = model(data)
            loss = criterion(output, target)
            loss.backward()
            optimizer.step()
            epoch_loss += loss.item()

        # Evaluate each epoch
        model.eval()
        all_preds, all_targets, all_probs = [], [], []
        with torch.no_grad():
            for data, target in test_loader:
                data, target = data.to(device), target.to(device)
                output = model(data)
                probs = torch.softmax(output, dim=1)
                preds = output.argmax(dim=1)
                all_preds.extend(preds.cpu().numpy())
                all_targets.extend(target.cpu().numpy())
                all_probs.extend(probs[:, 1].cpu().numpy())

        acc = accuracy_score(all_targets, all_preds)
        f1 = f1_score(all_targets, all_preds, average='weighted', zero_division=0)
        precision = precision_score(all_targets, all_preds, average='weighted', zero_division=0)
        recall = recall_score(all_targets, all_preds, average='weighted', zero_division=0)

        try:
            auc = roc_auc_score(all_targets, all_probs)
        except ValueError:
            auc = 0.0

        avg_loss = epoch_loss / len(train_loader)
        history.append({
            'epoch': epoch + 1,
            'loss': avg_loss,
            'accuracy': acc,
            'f1_score': f1,
            'precision': precision,
            'recall': recall,
            'auc_roc': auc,
        })

        if (epoch + 1) % 5 == 0 or epoch == 0:
            print(f"  Epoch {epoch+1}/{total_epochs}: loss={avg_loss:.4f}, acc={acc:.4f}, f1={f1:.4f}, auc={auc:.4f}")

    # Final evaluation
    print(f"\n[4/4] Final evaluation...")
    final = history[-1]
    cm = confusion_matrix(all_targets, all_preds)

    # Compute detection rate (recall for attack class=1) and FPR
    tn, fp, fn, tp = cm.ravel() if cm.size == 4 else (0, 0, 0, 0)
    detection_rate = tp / (tp + fn) if (tp + fn) > 0 else 0
    fpr = fp / (fp + tn) if (fp + tn) > 0 else 0

    results = {
        'model_type': model_type,
        'total_samples': len(merged),
        'train_samples': len(X_train),
        'test_samples': len(X_test),
        'total_epochs': total_epochs,
        'total_params': total_params,
        'final_accuracy': final['accuracy'],
        'final_f1': final['f1_score'],
        'final_precision': final['precision'],
        'final_recall': final['recall'],
        'final_auc_roc': final['auc_roc'],
        'detection_rate': detection_rate,
        'false_positive_rate': fpr,
        'confusion_matrix': cm.tolist(),
    }

    print(f"\n{'='*60}")
    print(f"CENTRALIZED RESULTS ({model_type})")
    print(f"{'='*60}")
    print(f"  Accuracy:       {final['accuracy']:.4f}")
    print(f"  F1 Score:       {final['f1_score']:.4f}")
    print(f"  Precision:      {final['precision']:.4f}")
    print(f"  Recall:         {final['recall']:.4f}")
    print(f"  AUC-ROC:        {final['auc_roc']:.4f}")
    print(f"  Detection Rate: {detection_rate:.4f}")
    print(f"  FPR:            {fpr:.4f}")
    print(f"{'='*60}")

    # Save
    with open(os.path.join(results_dir, "centralized_results.json"), 'w') as f:
        json.dump(results, f, indent=2)

    pd.DataFrame(history).to_csv(os.path.join(results_dir, "centralized_history.csv"), index=False)

    # Save model
    os.makedirs(os.path.join(_PROJECT_ROOT, "models"), exist_ok=True)
    torch.save(model.state_dict(), os.path.join(_PROJECT_ROOT, "models", "centralized_model.pth"))

    print(f"\nResults saved to {results_dir}/")
    return results, history


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Centralized Baseline Training")
    parser.add_argument("--config", type=str, default="config/local_test_config.yaml")
    args = parser.parse_args()

    with open(args.config, 'r') as f:
        config = yaml.safe_load(f)

    train_centralized(config)
