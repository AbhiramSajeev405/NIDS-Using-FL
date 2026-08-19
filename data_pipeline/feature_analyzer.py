"""
feature_analyzer.py

This script analyzes the header rows of the 9 heterogeneous NIDS datasets.
It uses a "Rosetta Stone" mapping to convert dataset-specific acronyms into
a standardized language, and then computationally finds the true mathematical
intersection (the columns that exist in ALL 9 datasets).

This replaces hardcoded feature lists with empirical data science.
"""

import os
import pandas as pd
from collections import defaultdict

# 1. Provide the paths to your downloaded CSVs (even if they are 11GB, 
# this script only reads line 1, so it runs instantly).
DATASET_PATHS = {
    "CIC-IDS-2017": "../data/raw/CIC-IDS-2017.csv",
    "CSE-CIC-IDS2018": "../data/raw/CSE-CIC-IDS2018.csv",
    "UNSW-NB15": "../data/raw/UNSW-NB15.csv",
    "Edge-IIoTset": "../data/raw/Edge-IIoTset.csv",
    "UGR16": "../data/raw/UGR16.csv",
    "ISCX-VPN": "../data/raw/ISCX-VPN.csv",
    "IoT-23": "../data/raw/IoT-23.csv",
    "TON_IoT": "../data/raw/TON_IoT.csv",
    "BoT-IoT": "../data/raw/BoT-IoT.csv"
}

# 2. The Rosetta Stone Dictionary
# Maps weird dataset-specific column names to a perfectly standard English name.
# We map them all to lowercase with underscores.
ROSETTA_STONE = {
    # == Protocols ==
    "proto": "protocol",
    " Protocol": "protocol",
    
    # == Ports ==
    " Destination Port": "dst_port",
    "dstport": "dst_port",
    "id.resp_p": "dst_port",
    "dport": "dst_port",

    " Source Port": "src_port",
    "srcport": "src_port",
    "id.orig_p": "src_port",
    "sport": "src_port",

    # == Durations ==
    " Flow Duration": "flow_duration",
    "dur": "flow_duration",
    "duration": "flow_duration",

    # == Packet Counts ==
    " Total Fwd Packets": "fwd_packets",
    "spkts": "fwd_packets",
    "orig_pkts": "fwd_packets",
    "src_pkts": "fwd_packets",

    " Total Backward Packets": "bwd_packets",
    "dpkts": "bwd_packets",
    "resp_pkts": "bwd_packets",
    "dst_pkts": "bwd_packets",

    # == Bytes ==
    "Total Length of Fwd Packets": "fwd_bytes",
    "sbytes": "fwd_bytes",
    "orig_bytes": "fwd_bytes",
    "src_bytes": "fwd_bytes",

    " Total Length of Bwd Packets": "bwd_bytes",
    "dbytes": "bwd_bytes",
    "resp_bytes": "bwd_bytes",
    "dst_bytes": "bwd_bytes",

    # Add more mappings as you discover the raw column names!
}


def analyze_features():
    print("==================================================")
    print(" FL-NIDS Feature Intersection Analyzer")
    print("==================================================")

    dataset_features = {}
    missing_files = []

    # Read the headers
    for name, path in DATASET_PATHS.items():
        if not os.path.exists(path):
            missing_files.append((name, path))
            continue
            
        try:
            # Read ONLY the first row (nrows=0) to get the columns instantly
            df = pd.read_csv(path, nrows=0)
            raw_columns = df.columns.tolist()
            
            # Translate the raw columns using the Rosetta Stone
            translated_cols = set()
            for col in raw_columns:
                clean_col = str(col).strip()
                if clean_col in ROSETTA_STONE:
                    translated_cols.add(ROSETTA_STONE[clean_col])
                else:
                    # If it's not in the dictionary, just keep the raw lowercase name
                    translated_cols.add(clean_col.lower().replace(" ", "_"))
            
            dataset_features[name] = translated_cols
            print(f"[*] {name}: Found {len(raw_columns)} raw columns -> {len(translated_cols)} translated features.")
            
        except Exception as e:
            print(f"[!] Error reading {name}: {e}")

    if missing_files:
        print("\n[!] Waiting for the following datasets to be downloaded and placed correctly:")
        for name, path in missing_files:
            print(f"    - {name} (Expected at: {path})")
        print("\nPlease download the CSVs and update DATASET_PATHS before running the intersection.")
        return

    print("\nComputing absolute mathematical intersection across all 9 datasets...")
    
    # Calculate the intersection of all sets
    if not dataset_features:
        return
        
    common_features = set.intersection(*dataset_features.values())
    
    print("\n==================================================")
    print(f" FINAL RESULT: Found {len(common_features)} Universal Features")
    print("==================================================")
    
    for i, feature in enumerate(sorted(common_features)):
        print(f" {i+1:02d}. {feature}")
        
    print("\n[Recommendation] Update dataset_aligner.py UNIVERSAL_FEATURES with this exact list.")

if __name__ == "__main__":
    analyze_features()
