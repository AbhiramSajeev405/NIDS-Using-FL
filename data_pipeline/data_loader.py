import os
import pandas as pd
import torch
import numpy as np
from torch.utils.data import Dataset, DataLoader
from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import train_test_split

class UnifiedNIDSDataset(Dataset):
    def __init__(self, data_path, scaler=None, fit_scaler=False):
        self.data_path = data_path
        # Read protocol as object (string), rest as float32
        self.df = pd.read_csv(data_path, dtype={'protocol': object})
        # Convert protocol to numeric: tcp=6, udp=17, icmp=1, arp=0, etc.
        protocol_map = {'tcp': 6, 'udp': 17, 'icmp': 1, 'arp': 0, 'sctp': 132, 'unknown': 99}
        if 'protocol' in self.df.columns:
            self.df['protocol'] = self.df['protocol'].map(protocol_map).fillna(99).astype(np.float32)
        # Convert remaining columns to float32
        for col in self.df.columns:
            if self.df[col].dtype == object:
                self.df[col] = pd.to_numeric(self.df[col], errors='coerce').fillna(0).astype(np.float32)

        # Detect label column — try common names then fall back to last column
        if 'label' in self.df.columns:
            label_col = 'label'
        elif 'Label' in self.df.columns:
            label_col = 'Label'
        else:
            label_col = self.df.columns[-1]
            print(f"[DataLoader] Warning: No 'label' column found in {data_path}, using last column '{label_col}'")

        self.features = self.df.drop(label_col, axis=1).values
        self.labels = self.df[label_col].values

        self.scaler = scaler
        if fit_scaler and self.scaler is None:
            self.scaler = StandardScaler()
            self.features = self.scaler.fit_transform(self.features).astype(np.float32)
        elif self.scaler is not None:
            self.features = self.scaler.transform(self.features).astype(np.float32)

        self.features = torch.tensor(self.features, dtype=torch.float32)
        self.labels = torch.tensor(self.labels, dtype=torch.long)

    def __len__(self):
        return len(self.labels)

    def __getitem__(self, idx):
        return self.features[idx], self.labels[idx]

def get_dataloader(data_path, batch_size=32, test_split=0.2, seed=None):
    """Loads a client's CSV and splits it into train/test DataLoaders."""
    # Read protocol as object (string), rest as float32
    df = pd.read_csv(data_path, dtype={'protocol': object})
    # Convert protocol to numeric: tcp=6, udp=17, icmp=1, arp=0, etc.
    protocol_map = {'tcp': 6, 'udp': 17, 'icmp': 1, 'arp': 0, 'sctp': 132, 'unknown': 99}
    if 'protocol' in df.columns:
        df['protocol'] = df['protocol'].map(protocol_map).fillna(99).astype(np.float32)
    # Convert remaining columns to float32
    for col in df.columns:
        if df[col].dtype == object:
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0).astype(np.float32)
    # Replace infinities with 0
    df = df.replace([np.inf, -np.inf], 0)
    # Fill any remaining NaN values with 0
    df = df.fillna(0)

    # Detect label column — try common names then fall back to last column
    if 'label' in df.columns:
        label_col = 'label'
    elif 'Label' in df.columns:
        label_col = 'Label'
    else:
        label_col = df.columns[-1]
        print(f"[DataLoader] Warning: No 'label' column found in {data_path}, using last column '{label_col}'")

    X = df.drop(label_col, axis=1).values
    y = df[label_col].values

    # Split
    if seed is None:
        seed = 42
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=test_split, random_state=seed)

    # Scale
    scaler = StandardScaler()
    X_train = scaler.fit_transform(X_train).astype(np.float32)
    X_test = scaler.transform(X_test).astype(np.float32)

    # To Tensors
    X_train = torch.tensor(X_train, dtype=torch.float32)
    y_train = torch.tensor(y_train, dtype=torch.long)
    X_test = torch.tensor(X_test, dtype=torch.float32)
    y_test = torch.tensor(y_test, dtype=torch.long)

    # Datasets
    class SimpleDataset(Dataset):
        def __init__(self, X, y):
            self.X = X
            self.y = y
        def __len__(self): return len(self.y)
        def __getitem__(self, idx): return self.X[idx], self.y[idx]

    train_dataset = SimpleDataset(X_train, y_train)
    test_dataset = SimpleDataset(X_test, y_test)

    train_loader = DataLoader(train_dataset, batch_size=batch_size, shuffle=True)
    test_loader = DataLoader(test_dataset, batch_size=batch_size, shuffle=False)

    return train_loader, test_loader, scaler
