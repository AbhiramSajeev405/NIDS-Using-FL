"""
dataset_aligner.py

This script enforces the "Feature Intersection" strategy for Cross-Silo FL.
It takes 9 heterogeneous NIDS datasets (CIC-IDS, UNSW-NB15, IoT-23, etc.)
and maps them down to a universal 20-feature input vector (input_dim=20).

This guarantees that mathematically, the neural networks on all 9 clients 
will have the exact same architecture, allowing their weights to be averaged 
by the Global Server without dimension mismatch errors.
"""

import os
import pandas as pd
import numpy as np

# The Universal 20-Feature Schema
# Any feature not present in a raw dataset will be imputed with 0.
UNIVERSAL_FEATURES = [
    "Protocol",                # E.g., 6 (TCP), 17 (UDP)
    "Destination_Port",        # Target port
    "Flow_Duration",           # Total duration of the connection
    "Total_Fwd_Packets",       # Packets sent
    "Total_Bwd_Packets",       # Packets received
    "Total_Length_Fwd",        # Bytes sent
    "Total_Length_Bwd",        # Bytes received
    "Fwd_Packet_Length_Max",   
    "Fwd_Packet_Length_Min",
    "Fwd_Packet_Length_Mean",
    "Bwd_Packet_Length_Max",
    "Bwd_Packet_Length_Min",
    "Bwd_Packet_Length_Mean",
    "Flow_Bytes_s",
    "Flow_Packets_s",
    "FIN_Flag_Count",          # TCP Flags
    "SYN_Flag_Count",
    "RST_Flag_Count",
    "PSH_Flag_Count",
    "ACK_Flag_Count"
]

# Dictionary mapping specific dataset column names to our UNIVERSAL_FEATURES
# This is the "translation layer" for the 9 distinct datasets
COLUMN_MAPPINGS = {
    "CIC-IDS-2017": {
        "Protocol": "Protocol",
        " Destination Port": "Destination_Port",
        " Flow Duration": "Flow_Duration",
        " Total Fwd Packets": "Total_Fwd_Packets",
        " Total Backward Packets": "Total_Bwd_Packets",
        "Total Length of Fwd Packets": "Total_Length_Fwd",
        " Total Length of Bwd Packets": "Total_Length_Bwd",
        " Fwd Packet Length Max": "Fwd_Packet_Length_Max",
        " Fwd Packet Length Min": "Fwd_Packet_Length_Min",
        " Fwd Packet Length Mean": "Fwd_Packet_Length_Mean",
        "Bwd Packet Length Max": "Bwd_Packet_Length_Max",
        " Bwd Packet Length Min": "Bwd_Packet_Length_Min",
        " Bwd Packet Length Mean": "Bwd_Packet_Length_Mean",
        "Flow Bytes/s": "Flow_Bytes_s",
        " Flow Packets/s": "Flow_Packets_s",
        "FIN Flag Count": "FIN_Flag_Count",
        " SYN Flag Count": "SYN_Flag_Count",
        " RST Flag Count": "RST_Flag_Count",
        " PSH Flag Count": "PSH_Flag_Count",
        " ACK Flag Count": "ACK_Flag_Count",
        " Label": "Label"
    },
    "UNSW-NB15": {
        "proto": "Protocol",
        "dstport": "Destination_Port",
        "dur": "Flow_Duration",
        "spkts": "Total_Fwd_Packets",
        "dpkts": "Total_Bwd_Packets",
        "sbytes": "Total_Length_Fwd",
        "dbytes": "Total_Length_Bwd",
        "smean": "Fwd_Packet_Length_Mean", # Approximation
        "dmean": "Bwd_Packet_Length_Mean", # Approximation
        "label": "Label"
        # Notice UNSW doesn't explicitly log TCP flags in the same way,
        # so those will automatically become 0 for UNSW clients.
    },
    "IoT-23": {
        "proto": "Protocol",
        "id.resp_p": "Destination_Port",
        "duration": "Flow_Duration",
        "orig_pkts": "Total_Fwd_Packets",
        "resp_pkts": "Total_Bwd_Packets",
        "orig_bytes": "Total_Length_Fwd",
        "resp_bytes": "Total_Length_Bwd",
        "label": "Label"
    }
}

def align_dataset(df_raw: pd.DataFrame, dataset_type: str) -> pd.DataFrame:
    """
    Takes a raw dataframe from a specific dataset and maps it to the 20-feature schema.
    """
    if dataset_type not in COLUMN_MAPPINGS:
        raise ValueError(f"Unknown dataset type! {dataset_type}")
        
    mapping = COLUMN_MAPPINGS[dataset_type]
    
    # Create an empty dataframe with our target schema (+ the Label)
    aligned_df = pd.DataFrame(columns=UNIVERSAL_FEATURES + ["Label"])
    
    # Fill in the columns we DO have a mapping for
    for raw_col, universal_col in mapping.items():
        if raw_col in df_raw.columns:
            aligned_df[universal_col] = df_raw[raw_col]
        else:
            print(f"[WARN] Expected column '{raw_col}' not found in {dataset_type} file.")
            
    # For columns we DID NOT map (because the dataset doesn't have them), fill with 0
    aligned_df.fillna(0, inplace=True)
    
    # Clean up any "Infinity" or "NaN" values that CIC-IDS is notorious for
    aligned_df.replace([np.inf, -np.inf], 0, inplace=True)
    aligned_df.fillna(0, inplace=True)
    
    # Ensure binary labeling (0 = Benign, 1 = Attack)
    # Different datasets use different strings for attacks.
    if aligned_df['Label'].dtype == object:
        aligned_df['Label'] = aligned_df['Label'].apply(
            lambda x: 0 if str(x).lower() in ['normal', 'benign', '0'] else 1
        )
        
    return aligned_df

if __name__ == "__main__":
    print("Dataset Aligner Schema Tool Loaded.")
    print(f"Target Feature Dimension: {len(UNIVERSAL_FEATURES)} columns.")
    print("Ready to map heterogeneous PCAP/CSV files to universal tensors.")
