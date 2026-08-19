# LSCUDAPORT - Federated Learning Network Intrusion Detection System

## What This Is

A privacy-preserving Network Intrusion Detection System (NIDS) that trains machine learning models across 9 distributed clients without sharing raw network traffic data.

## Key Features

- **5 Model Architectures**: MLP, CNN, LSTM, ResNet, AutoEncoder
- **6 Aggregation Algorithms**: FedAvg, FedProx, FedMedian, Trimmed Mean, Krum, FedNova
- **9 Heterogeneous Datasets**: Bot-IoT, CIC-IDS-2017, Edge-IIoTSet, UNSW-NB15, TON-IoT, etc.
- **Two Architectures**: Flat (baseline) or Hierarchical (regional aggregation)
- **Real-time Dashboard**: Live training visualization

## Quick Start

```bash
# Install dependencies
pip install -r requirements.txt

# Run quick test (2 clients, 3 rounds)
python test_runner.py

# Start dashboard
streamlit run utils/dashboard_streamlit.py

# Start global server (in new terminal)
python federated/server_global.py --port 8080 --config config/physical_config.yaml --min_clients 2

# Start clients (in new terminals)
python federated/client.py --cid Client_01 --server_ip 127.0.0.1 --port 8080
python federated/client.py --cid Client_02 --server_ip 127.0.0.1 --port 8080
```

## Documentation

| Document | Purpose |
|----------|---------|
| `RESEARCH_PAPER.md` | Full academic paper with methodology, experiments, findings |
| `QUICK_REFERENCE.md` | Commands, configs, troubleshooting |
| `CODEBASE_OVERVIEW.md` | Technical system documentation |

## Results Summary

| Metric | Value |
|--------|-------|
| Accuracy | 86.2% |
| Attack Detection Rate | 100% |
| False Positive Rate | 27.6% |
| Training Time (15 rounds) | ~12 minutes |

## Critical Lessons Learned

1. **Class-weighted loss is essential** for imbalanced security datasets
2. **Always inspect for data leakage** before training
3. **Byzantine-robust aggregation** defends against poisoning attacks

## Project Structure

```
LSCUDAPORT/
├── federated/          # FL server, client, strategies
├── models/             # Neural network architectures
├── data_pipeline/      # Data loading and alignment
├── simulation/         # Experiment runners
├── utils/              # Metrics, dashboard, logging
├── config/             # YAML configurations
└── data/processed/     # Client datasets (CSV)
```

## Citation

If you use this system, please cite the research paper (`RESEARCH_PAPER.md`).
