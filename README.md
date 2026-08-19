# Federated Learning-Based Network Intrusion Detection System

A privacy-preserving **Network Intrusion Detection System (NIDS)** developed by our team using **Federated Learning (FL)** to collaboratively train intrusion detection models across distributed network clients without sharing their raw network traffic data.

As an academic team project, we explored heterogeneous cybersecurity datasets, multiple deep-learning architectures, federated aggregation strategies, attack simulation, defensive mechanisms, and real-time training monitoring.
---

## 📌 Overview

Traditional machine-learning-based intrusion detection often requires network data from multiple sources to be collected in a centralized location. This can introduce privacy, security, and data-sharing concerns.

This project explores an alternative approach using **Federated Learning**, where each client trains a model locally using its own network traffic data and sends only model updates to a federated server.

The server aggregates these updates to improve a shared global intrusion detection model.

The experimental environment supports:

- **9 distributed network clients**
- **5 neural network architectures**
- **6 federated aggregation strategies**
- Heterogeneous cybersecurity datasets
- Flat and hierarchical federated architectures
- Attack and poisoning simulations
- Federated-learning defense mechanisms
- Real-time training monitoring
- Automated experiment execution

---

## ✨ Key Features

### Federated Intrusion Detection

Network traffic remains on individual clients while model parameters are exchanged with the federated server.

### Multiple Deep Learning Models

The system supports:

- Multi-Layer Perceptron (MLP)
- Convolutional Neural Network (CNN)
- Long Short-Term Memory Network (LSTM)
- Residual Network (ResNet)
- Autoencoder

### Multiple Federated Aggregation Strategies

Six aggregation strategies are supported:

- FedAvg
- FedProx
- FedMedian
- Trimmed Mean
- Krum
- FedNova

This enables comparison between conventional aggregation methods and strategies designed to provide greater robustness against abnormal or malicious client updates.

### Heterogeneous Client Data

Clients can train using different cybersecurity datasets, creating a **non-identical distributed data environment** closer to real-world federated learning scenarios.

### Attack Simulation

The simulation framework supports experiments involving:

- Model poisoning
- Label flipping
- Evasion scenarios
- Malicious client behavior

### Federated Learning Defenses

Experimental defensive mechanisms include:

- Gradient clipping
- Differential privacy
- Poisoned-update detection
- Client contribution evaluation

### Real-Time Monitoring

Dashboard components provide visibility into federated training and experimental activity.

---

# 🏗️ System Architecture

The basic federated-learning workflow is:

```text
                         ┌─────────────────────┐
                         │    Global Server    │
                         │                     │
                         │ Aggregates Client   │
                         │ Model Updates       │
                         └──────────┬──────────┘
                                    │
                  ┌─────────────────┼─────────────────┐
                  │                 │                 │
                  ▼                 ▼                 ▼
             Client Group      Client Group      Client Group
                  │                 │                 │
             Local Data        Local Data        Local Data
                  │                 │                 │
             Local Model       Local Model       Local Model
              Training          Training          Training
                  │                 │                 │
                  └─────────────────┼─────────────────┘
                                    │
                              Model Updates
                                    │
                                    ▼
                              Global Model
```

Each client:

1. Receives the current global model.
2. Loads its local network dataset.
3. Trains the model locally.
4. Sends model parameters/updates to the server.
5. Keeps its raw network data locally.

The server aggregates participating client updates and produces a new global model for the next communication round.

---

# 🌐 Federated Architecture

The project supports two deployment approaches.

### Flat Architecture

```text
Client 01 ─┐
Client 02 ─┤
Client 03 ─┤
Client 04 ─┤
Client 05 ─┼──► Global Federated Server
Client 06 ─┤
Client 07 ─┤
Client 08 ─┤
Client 09 ─┘
```

All participating clients communicate directly with one global federated server.

### Hierarchical Architecture

The project also includes support for organizing clients into regional/country-level groups before global aggregation.

```text
Clients ──► Country/Regional Servers ──► Global Server
```

This architecture can be used to investigate more distributed federated-learning environments.

---

# 📊 Dataset Environment

The experimental setup was designed around multiple heterogeneous cybersecurity datasets distributed across nine clients.

Examples include:

| Client | Dataset | Samples |
|---|---|---:|
| Client 01 | Bot-IoT | 50,000 |
| Client 02 | CIC-IDS-2017 | 50,000 |
| Client 03 | Edge-IIoTSet | 50,000 |
| Client 04 | CSE-CIC-IDS2018 | 50,000 |
| Client 05 | Scenario-B | 18,758 |
| Client 06 | UNSW-NB15 | 50,000 |
| Client 07 | CIC-PortScan | 50,000 |
| Client 08 | IDS2018-Day2 | 50,000 |
| Client 09 | TON-IoT | 50,000 |

The documented experimental setup contains approximately **418,758 network traffic samples** distributed across the clients.

> Raw/processed datasets are not included in this repository because of their size and to keep the repository lightweight.

---

## 🔄 Data Preprocessing

Different intrusion-detection datasets often contain different feature structures.

The project's data pipeline performs feature alignment and preprocessing before federated training.

Processing includes:

- CSV data loading
- Protocol conversion
- Missing/infinite value handling
- Feature alignment
- Feature normalization
- Stratified train/test splitting
- PyTorch DataLoader generation

A unified representation of **78 features** is used in the documented experimental setup.

Example protocol mapping:

```text
TCP  → 6
UDP  → 17
ICMP → 1
ARP  → 0
```

---

# 🧠 Model Architectures

## MLP

A Multi-Layer Perceptron provides a fully connected baseline for binary intrusion classification.

Example architecture:

```text
78 Input Features
       │
       ▼
Linear (78 → 128)
       │
     ReLU
       │
  Dropout (0.3)
       │
       ▼
Linear (128 → 64)
       │
     ReLU
       │
  Dropout (0.3)
       │
       ▼
 Linear (64 → 2)
       │
       ▼
Benign / Attack
```

## CNN

The CNN model applies convolutional operations to network feature representations to learn local patterns in traffic data.

## LSTM

The LSTM architecture is included to explore sequential and time-dependent patterns associated with network attacks.

## ResNet

Residual connections enable experimentation with deeper architectures while improving gradient flow.

## Autoencoder

The Autoencoder provides an unsupervised approach for learning representations of network traffic and investigating anomaly detection through reconstruction behavior.

---

# 🔄 Federated Aggregation Strategies

| Strategy | Purpose |
|---|---|
| **FedAvg** | Weighted averaging of client model updates |
| **FedProx** | Adds a proximal term to reduce client drift |
| **FedMedian** | Uses coordinate-wise median aggregation |
| **Trimmed Mean** | Removes extreme client values before averaging |
| **Krum** | Selects an update based on similarity to other client updates |
| **FedNova** | Normalizes client updates based on local training |

The availability of multiple strategies allows experiments comparing standard federated learning with approaches intended to handle heterogeneous or potentially malicious participants.

---

# 🛡️ Security and Robustness Experiments

The project includes components for investigating security challenges specific to federated learning.

## Poisoning Simulation

Malicious clients can be simulated to investigate how manipulated updates affect global-model performance.

## Label Flipping

Training labels can be altered to simulate compromised clients.

## Gradient Clipping

Gradient/update magnitude can be restricted to reduce the effect of unusually large updates.

## Differential Privacy

Noise-based mechanisms are included for experimentation with additional privacy protection.

## Poison Detection

Client updates can be examined for anomalous behavior before aggregation.

## Contribution Evaluation

Client contribution mechanisms can be used to investigate differences in participant reliability and data quality.

---

# 📈 Experimental Results

One documented March 2026 experiment produced the following results:

| Metric | Result |
|---|---:|
| Accuracy | **86.2%** |
| Attack Detection Rate | **100%** |
| False Positive Rate | **27.6%** |
| Training Time (15 rounds) | **~12 minutes** |

> These values represent a documented experimental configuration and should not be interpreted as the performance of every model, dataset, or aggregation strategy in the repository.

Detailed experimental outputs and comparison files are available in the results-related directories.

---

# 🔬 Important Experimental Findings

During development, two important machine-learning issues were identified.

### Data Leakage

An earlier dataset configuration contained information that directly exposed the target label.

This produced misleadingly high accuracy of approximately **99.99%**.

The leaking feature was removed and the feature set was rebuilt before subsequent evaluation.

### Class Imbalance and Model Collapse

Another experiment produced a model that primarily predicted benign traffic because of severe class imbalance.

Class-weighted loss was introduced to give greater importance to underrepresented attack samples.

These issues reinforced the importance of evaluating security models using more than accuracy alone, including confusion-matrix behavior, detection rate, and false-positive rate.

---

# 📡 Monitoring Dashboard

The project contains dashboard components for monitoring federated-learning experiments.

Technologies used include:

- FastAPI
- Streamlit
- WebSockets
- Uvicorn

Depending on the selected dashboard implementation, training information and experiment status can be visualized while the federated system is running.

---

# 🛠️ Technology Stack

| Category | Technology |
|---|---|
| Programming Language | Python |
| Federated Learning | Flower |
| Deep Learning | PyTorch |
| Machine Learning | scikit-learn |
| Data Processing | Pandas, NumPy |
| Configuration | YAML |
| API / Dashboard | FastAPI |
| Visualization / Dashboard | Streamlit |
| Server | Uvicorn |
| Real-Time Communication | WebSockets |
| Version Control | Git / GitHub |

---

# 📁 Project Structure

```text
NIDS-Using-FL/
│
├── config/
│   └── Experiment and deployment configurations
│
├── dashboard/
│   └── Real-time monitoring components
│
├── data_pipeline/
│   ├── Data loading
│   ├── Feature alignment
│   └── Dataset preprocessing
│
├── deployment/
│   └── Distributed deployment utilities
│
├── federated/
│   ├── Global server
│   ├── Federated clients
│   ├── Aggregation strategies
│   └── Defense mechanisms
│
├── models/
│   ├── MLP
│   ├── CNN
│   ├── LSTM
│   ├── ResNet
│   └── Autoencoder
│
├── simulation/
│   ├── Attack simulation
│   ├── Experiment execution
│   └── Ablation studies
│
├── utils/
│   ├── Metrics
│   ├── Experiment management
│   ├── Drift detection
│   └── Monitoring utilities
│
├── experiment_results/
├── results/
├── requirements.txt
└── README.md
```

---

# ⚙️ Installation

## 1. Clone the Repository

```bash
git clone https://github.com/AbhiramSajeev405/NIDS-Using-FL.git
cd NIDS-Using-FL
```

## 2. Create a Virtual Environment

### Windows

```bash
python -m venv venv
venv\Scripts\activate
```

### Linux/macOS

```bash
python3 -m venv venv
source venv/bin/activate
```

## 3. Install Dependencies

```bash
pip install -r requirements.txt
```

---

# ▶️ Running the Project

A basic federated setup requires one server and multiple clients.

### Start the Global Server

```bash
python federated/server_global.py --port 8080 --config config/physical_config.yaml --min_clients 2
```

### Start Client 01

Open another terminal:

```bash
python federated/client.py --cid Client_01 --server_ip 127.0.0.1 --port 8080 --config config/physical_config.yaml
```

### Start Client 02

Open another terminal:

```bash
python federated/client.py --cid Client_02 --server_ip 127.0.0.1 --port 8080 --config config/physical_config.yaml
```

Additional clients can be started using their corresponding client IDs and configurations.

---

# ⚠️ Current Compatibility Note

The project documentation identifies a compatibility issue with newer versions of **Flower**.

The current codebase uses Flower's legacy `start_server()` / `start_client()` style APIs. Testing with Flower 1.27.0 identified a situation where the server starts and clients connect, but initialization can stall while requesting initial model parameters.

The federated client/server implementation therefore requires migration or compatibility testing with the appropriate Flower API/version before the complete environment can be considered fully reproducible on a fresh installation.

This repository should currently be considered an **academic/research implementation and experimental testbed**, rather than a production NIDS.

---
# 🚀 Future Improvements

Planned areas for further development include:

- Migration to the current Flower application/API architecture
- Reduction of false-positive rate
- Expanded adversarial federated-learning experiments
- Improved poisoned-client detection
- Additional privacy-preserving mechanisms
- Automated experiment pipelines
- Containerized deployment using Docker
- Kubernetes-based federated deployment
- Cloud-based distributed client/server testing
- CI/CD pipeline for automated testing
- Improved experiment visualization and reporting

---
# 📚 Project Context

This project was developed by our team as an academic exploration of **Federated Learning for Network Intrusion Detection**, focusing on privacy-preserving collaborative training across heterogeneous network environments.

Our objective was to investigate how distributed organizations or network environments could collaboratively improve intrusion detection models without directly exchanging their raw network traffic datasets.

---
## 👥 Project Team

This project was designed and developed collaboratively by our four-member academic project team. We worked together on the development, experimentation, testing, and documentation of the Federated Learning-based Network Intrusion Detection System.

| Team Member | GitHub |
|-------------|--------|
| **Abhiram Sajeev** | [@AbhiramSajeev405](https://github.com/AbhiramSajeev405) |
| **Adarsh S J** | [@Horcrux123](https://github.com/Horcrux123) |
| **Alfin Jerome** | [@alfinjerome](https://github.com/alfinjerome) |
| **Alen J S** | [@thereelalen](https://github.com/thereelalen) |

> This repository represents the collaborative work of all four team members.
---

> **Note:** This repository is intended for academic, research, and portfolio purposes.