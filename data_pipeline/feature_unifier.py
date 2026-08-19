import os
import yaml
import numpy as np
import pandas as pd
from sklearn.preprocessing import StandardScaler

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class FeatureUnifier:
    def __init__(self, config_path=None):
        if config_path is None:
            config_path = os.path.join(_PROJECT_ROOT, "config", "dataset_mappings.yaml")
        with open(config_path, 'r') as f:
            self.config = yaml.safe_load(f)
        self.unified_features = self.config['unified_features']
        self.dummy_bounds = self.config['dummy_data_bounds']
        self.label_mapping = self.config['label_mapping']

    def generate_dummy_data(self, num_samples, out_path, client_id, is_attacker=False,
                            benign_ratio=0.9, attack_ratio=0.1, total_features=78):
        """Generates dummy data in the Unified Feature Space, padding up to total_features."""
        print(f"Generating dummy data for {client_id} (Attacker: {is_attacker}, Features: {total_features})...")
        data = {}
        for feature in self.unified_features:
            low, high = self.dummy_bounds.get(feature, [0, 100])
            shift = np.random.randint(-10, 10) if feature != 'protocol' else 0
            if feature in ['psh_flag_cnt', 'ack_flag_cnt']:
                data[feature] = np.random.randint(low, high + 1, num_samples)
            else:
                data[feature] = np.random.uniform(max(0, low + shift), max(0, high + shift), num_samples)

        # Pad with dummy numeric features until we hit the total expected by the model
        for i in range(len(self.unified_features), total_features):
            data[f'feature_{i}'] = np.random.uniform(0, 100, num_samples)

        df = pd.DataFrame(data)

        if is_attacker:
            df['label'] = np.random.choice([0, 1], num_samples, p=[0.1, 0.9])
        else:
            df['label'] = np.random.choice([0, 1], num_samples, p=[benign_ratio, attack_ratio])

        os.makedirs(os.path.dirname(out_path), exist_ok=True)
        df.to_csv(out_path, index=False)
        print(f"Saved dummy data to {out_path}")
        return df

    def generate_unified_pool(self, num_samples=50000, total_features=78):
        """Generate a single large pool of unified data for splitting, padding up to total_features."""
        data = {}
        for feature in self.unified_features:
            low, high = self.dummy_bounds.get(feature, [0, 100])
            if feature in ['psh_flag_cnt', 'ack_flag_cnt']:
                data[feature] = np.random.randint(low, high + 1, num_samples)
            else:
                data[feature] = np.random.uniform(low, high, num_samples)
                
        # Pad with dummy numeric features
        for i in range(len(self.unified_features), total_features):
            data[f'feature_{i}'] = np.random.uniform(0, 100, num_samples)
            
        df = pd.DataFrame(data)
        df['label'] = np.random.choice([0, 1], num_samples, p=[0.8, 0.2])
        return df



def prepare_all_dummy_data(base_dir=None, config=None):
    """Generate dummy data for all clients, respecting data distribution config.

    If config specifies Non-IID distribution, generates a single pool and
    splits it using the data_splitter module.
    """
    if base_dir is None:
        base_dir = _PROJECT_ROOT

    # Load experiment config if provided
    data_cfg = {}
    if config is not None:
        data_cfg = config.get('data', {})

    # Set seed for reproducibility
    seed = 42
    if config is not None:
        seed = config.get('experiment', {}).get('seed', 42)
    np.random.seed(seed)

    unifier = FeatureUnifier(os.path.join(base_dir, "config", "dataset_mappings.yaml"))
    processed_dir = os.path.join(base_dir, "data", "processed")
    os.makedirs(processed_dir, exist_ok=True)

    distribution = data_cfg.get('distribution', 'iid').lower()

    if distribution == 'non_iid' and config is not None:
        # Generate a single large pool and split with Dirichlet
        print("[FeatureUnifier] Generating pooled data for Non-IID splitting...")
        pool_df = unifier.generate_unified_pool(num_samples=500000, total_features=config.get('input_dim', 78) if config else 78)

        from data_pipeline.data_splitter import split_data, save_splits
        client_ids = [f"Client_{i:02d}" for i in range(1, 10)]
        client_dfs = split_data(pool_df, n_clients=9, config=config, seed=seed)
        save_splits(client_dfs, processed_dir, client_ids)
    else:
        # Original IID-style generation with heterogeneous sizes
        total_features = config.get('input_dim', 78) if config else 78
        for i in range(1, 10):
            client_id = f"Client_{i:02d}"
            out_path = os.path.join(processed_dir, f"{client_id}.csv")
            if i <= 3:
                num_samples = 50000
            elif i <= 6:
                num_samples = 100000
            else:
                num_samples = 20000
            unifier.generate_dummy_data(num_samples, out_path, client_id, is_attacker=False, total_features=total_features)

    # Attacker data (always generated)
    attacker_path = os.path.join(processed_dir, "Attacker.csv")
    total_features = config.get('input_dim', 78) if config else 78
    unifier.generate_dummy_data(20000, attacker_path, "Attacker", is_attacker=True, total_features=total_features)


if __name__ == "__main__":
    import sys
    # Optionally pass a config file to use Non-IID splitting
    if len(sys.argv) > 1:
        config_path = sys.argv[1]
        with open(config_path, 'r') as f:
            config = yaml.safe_load(f)
        prepare_all_dummy_data(config=config)
    else:
        prepare_all_dummy_data()
