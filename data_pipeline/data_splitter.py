"""
Non-IID Data Splitting for Federated Learning.

Partitions a unified dataset across N clients with configurable
heterogeneity using a Dirichlet distribution.

Key concepts:
  - IID: All clients get a uniform random split (similar class distributions)
  - Non-IID (Dirichlet): Lower alpha = more skewed class distributions per client
  - Label skew: Controls how many classes each client sees
  - Quantity skew: Controls how many samples each client gets

Reference: Hsu et al. 'Measuring the Effects of Non-IID Data Distribution' (2019)
"""

import os
import numpy as np
import pandas as pd


def split_iid(df, n_clients, seed=42):
    """Split data uniformly at random across n_clients.

    Args:
        df: pandas DataFrame with features + 'label' column
        n_clients: Number of clients to split across
        seed: Random seed for reproducibility

    Returns:
        List of DataFrames, one per client
    """
    np.random.seed(seed)
    indices = np.random.permutation(len(df))
    splits = np.array_split(indices, n_clients)
    return [df.iloc[s].reset_index(drop=True) for s in splits]


def split_non_iid_dirichlet(df, n_clients, alpha=0.5, seed=42):
    """Split data using Dirichlet distribution for Non-IID partitioning.

    Lower alpha = more heterogeneous (extreme skew).
    alpha=100 ≈ IID split.
    alpha=0.1 = very few classes per client.

    Args:
        df: pandas DataFrame with features + 'label' column
        n_clients: Number of clients
        alpha: Dirichlet concentration parameter
        seed: Random seed

    Returns:
        List of DataFrames, one per client
    """
    np.random.seed(seed)
    labels = df['label'].values
    unique_labels = np.unique(labels)
    n_classes = len(unique_labels)

    # Group indices by class
    class_indices = {c: np.where(labels == c)[0] for c in unique_labels}

    # For each class, draw Dirichlet proportions for clients
    client_indices = [[] for _ in range(n_clients)]

    for c in unique_labels:
        indices_c = class_indices[c]
        np.random.shuffle(indices_c)

        # Draw proportions from Dirichlet(alpha)
        proportions = np.random.dirichlet([alpha] * n_clients)

        # Split indices according to proportions
        splits = (proportions * len(indices_c)).astype(int)

        # Fix rounding: assign remainder to random clients
        remainder = len(indices_c) - splits.sum()
        for _ in range(remainder):
            splits[np.random.randint(n_clients)] += 1

        # Assign indices
        start = 0
        for i in range(n_clients):
            end = start + splits[i]
            client_indices[i].extend(indices_c[start:end].tolist())
            start = end

    # Create DataFrames
    client_dfs = []
    for indices in client_indices:
        if len(indices) > 0:
            client_dfs.append(df.iloc[indices].reset_index(drop=True))
        else:
            # Ensure every client gets at least some data
            sample_indices = np.random.choice(len(df), size=max(10, len(df) // n_clients // 10))
            client_dfs.append(df.iloc[sample_indices].reset_index(drop=True))

    return client_dfs


def split_quantity_skew(df, n_clients, min_ratio=0.2, max_ratio=1.0, seed=42):
    """Split data with varying quantities per client.

    Each client gets a different number of samples, simulating
    heterogeneous dataset sizes in practice.

    Args:
        df: pandas DataFrame
        n_clients: Number of clients
        min_ratio: Minimum fraction of (total/n_clients) samples
        max_ratio: Maximum fraction of (total/n_clients) samples
        seed: Random seed

    Returns:
        List of DataFrames, one per client
    """
    np.random.seed(seed)
    total = len(df)
    indices = np.random.permutation(total)

    # Generate random sizes for each client
    base_size = total // n_clients
    sizes = np.random.uniform(min_ratio, max_ratio, n_clients)
    sizes = (sizes / sizes.sum() * total).astype(int)

    # Fix rounding
    remainder = total - sizes.sum()
    sizes[0] += remainder

    client_dfs = []
    start = 0
    for size in sizes:
        end = min(start + size, total)
        client_dfs.append(df.iloc[indices[start:end]].reset_index(drop=True))
        start = end

    return client_dfs


def split_data(df, n_clients, config, seed=42):
    """Main entry point: splits data according to config.

    Reads config['data']['distribution'] to choose the splitting strategy.

    Args:
        df: pandas DataFrame with features + 'label' column
        n_clients: Number of clients
        config: Full experiment config dict
        seed: Random seed

    Returns:
        List of DataFrames, one per client
    """
    data_cfg = config.get('data', {})
    distribution = data_cfg.get('distribution', 'iid').lower()
    alpha = data_cfg.get('dirichlet_alpha', 0.5)
    quantity_skew = data_cfg.get('quantity_skew', False)

    if distribution == 'iid':
        print(f"[DataSplitter] IID split across {n_clients} clients")
        client_dfs = split_iid(df, n_clients, seed)
    elif distribution == 'non_iid':
        print(f"[DataSplitter] Non-IID Dirichlet(α={alpha}) split across {n_clients} clients")
        client_dfs = split_non_iid_dirichlet(df, n_clients, alpha, seed)
    else:
        raise ValueError(f"Unknown distribution: {distribution}. Options: 'iid', 'non_iid'")

    if quantity_skew:
        # Re-sample each split to create size differences
        min_r = data_cfg.get('quantity_min_ratio', 0.3)
        max_r = data_cfg.get('quantity_max_ratio', 1.0)
        np.random.seed(seed + 1)
        for i in range(len(client_dfs)):
            ratio = np.random.uniform(min_r, max_r)
            n_keep = max(10, int(len(client_dfs[i]) * ratio))
            client_dfs[i] = client_dfs[i].sample(n=n_keep, random_state=seed).reset_index(drop=True)

    # Print distribution summary
    for i, cdf in enumerate(client_dfs):
        label_counts = cdf['label'].value_counts().to_dict()
        print(f"  Client {i+1}: {len(cdf)} samples, labels={label_counts}")

    return client_dfs


def save_splits(client_dfs, output_dir, client_ids=None):
    """Save each client's DataFrame as a CSV file.

    Args:
        client_dfs: List of DataFrames
        output_dir: Directory to save CSVs
        client_ids: Optional list of client IDs (e.g., ['Client_01', ...])
    """
    os.makedirs(output_dir, exist_ok=True)
    for i, df in enumerate(client_dfs):
        if client_ids:
            cid = client_ids[i]
        else:
            cid = f"Client_{i+1:02d}"
        path = os.path.join(output_dir, f"{cid}.csv")
        df.to_csv(path, index=False)
        print(f"Saved {cid}: {len(df)} samples to {path}")
