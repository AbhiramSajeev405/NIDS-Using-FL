"""
LSCUDAPORT - Centralized Configuration Defaults
Single source of truth for all default values (Fixes BUG #010).
"""

# Network defaults
DEFAULT_SERVER_IP = "127.0.0.1"
DEFAULT_GLOBAL_PORT = 8080
DEFAULT_DASHBOARD_PORT = 456

# Training defaults
DEFAULT_LEARNING_RATE = 0.001
DEFAULT_BATCH_SIZE = 256
DEFAULT_EPOCHS = 3
DEFAULT_WEIGHT_DECAY = 0.0

# Model defaults
DEFAULT_MODEL_TYPE = "mlp"
DEFAULT_INPUT_DIM = 78
DEFAULT_NUM_CLASSES = 2

# Federated learning defaults
DEFAULT_ARCHITECTURE = "flat"
DEFAULT_STRATEGY = "fedavg"
DEFAULT_NUM_ROUNDS = 15

# Aggregation algorithm defaults
DEFAULT_TRIM_RATIO = 0.1
DEFAULT_KRUM_MALICIOUS = 1
DEFAULT_FEDPROX_MU = 0.1

def get_default(key):
    """Get a default value by key name."""
    defaults = {
        'server_ip': DEFAULT_SERVER_IP,
        'global_port': DEFAULT_GLOBAL_PORT,
        'dashboard_port': DEFAULT_DASHBOARD_PORT,
        'lr': DEFAULT_LEARNING_RATE,
        'batch_size': DEFAULT_BATCH_SIZE,
        'epochs': DEFAULT_EPOCHS,
        'weight_decay': DEFAULT_WEIGHT_DECAY,
        'model_type': DEFAULT_MODEL_TYPE,
        'input_dim': DEFAULT_INPUT_DIM,
        'num_classes': DEFAULT_NUM_CLASSES,
        'architecture': DEFAULT_ARCHITECTURE,
        'strategy': DEFAULT_STRATEGY,
        'num_rounds': DEFAULT_NUM_ROUNDS,
        'trim_ratio': DEFAULT_TRIM_RATIO,
        'krum_malicious': DEFAULT_KRUM_MALICIOUS,
        'fedprox_mu': DEFAULT_FEDPROX_MU,
    }
    return defaults.get(key)
